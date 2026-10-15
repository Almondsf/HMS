'''
Subscription rules. Payments only count once Paystack (or a platform
operator) confirms them; the browser is never trusted. Each payment
reference counts once, however many times it arrives (verify + webhooks).
'''

import calendar
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from audit.recorder import Category, record

from . import paystack
from .models import Interval, PlanPrice, Subscription, SubscriptionPayment


def add_months(moment, months):
    month = moment.month - 1 + months
    year, month = moment.year + month // 12, month % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def period_after(start, interval):
    return add_months(start, 12 if interval == Interval.YEARLY else 1)


def start_trial(hospital, *, days=None, email=''):
    '''Every new hospital starts with a free trial.'''
    return Subscription.objects.get_or_create(
        hospital=hospital,
        defaults={
            'status': Subscription.Status.TRIALING,
            'current_period_end': timezone.now() + timedelta(days=days or settings.SUBSCRIPTION_TRIAL_DAYS),
            'billing_email': email or hospital.contact_email,
        },
    )[0]


def price_for(plan, interval):
    price = PlanPrice.objects.filter(plan=plan, interval=interval, is_active=True).first()
    if price is None:
        raise ValidationError({'plan': f'The {plan} plan is not available {interval}.'})
    return price


@transaction.atomic
def apply_payment(*, hospital, reference, source, plan, interval, amount, paid_at=None, note='', recorded_by=''):
    '''
    Extend the hospital's paid access by one interval and switch it to the
    paid plan. Idempotent on `reference`. Returns (payment, created).
    '''
    existing = SubscriptionPayment.objects.filter(reference=reference).first()
    if existing is not None:
        return existing, False

    subscription = Subscription.objects.select_for_update().filter(hospital=hospital).first() or start_trial(hospital)
    now = timezone.now()
    # Paying early adds to the remaining time; paying late starts from today
    starts = max(now, subscription.current_period_end)
    subscription.current_period_end = period_after(starts, interval)
    subscription.status = Subscription.Status.ACTIVE
    subscription.interval = interval
    subscription.cancel_at_period_end = False
    subscription.save()

    if hospital.plan != plan:
        type(hospital).objects.filter(pk=hospital.pk).update(plan=plan)
        hospital.plan = plan

    payment = SubscriptionPayment.objects.create(
        hospital=hospital,
        reference=reference,
        source=source,
        plan=plan,
        interval=interval,
        amount=amount,
        paid_at=paid_at or now,
        period_end=subscription.current_period_end,
        note=note,
        recorded_by=recorded_by,
    )
    record(
        'subscription.payment_applied', Category.DOMAIN, resource=subscription,
        metadata={'reference': reference, 'plan': plan, 'interval': interval, 'amount': str(amount), 'source': source},
    )  # fmt: skip
    return payment, True


# ---- Paystack checkout ----


def start_checkout(*, hospital, plan, interval, email, callback_url):
    '''Create a Paystack checkout. Returns the URL to send the payer to.'''
    price = price_for(plan, interval)
    reference = f'hms-{hospital.schema_name}-{uuid.uuid4().hex[:12]}'
    result = paystack.initialize_transaction(
        email=email,
        amount_kobo=price.amount_kobo,
        reference=reference,
        callback_url=callback_url,
        plan_code=price.paystack_plan_code,  # with a plan code, Paystack renews automatically
        metadata={'hospital_id': hospital.pk, 'plan': plan, 'interval': interval},
    )
    Subscription.objects.filter(hospital=hospital).update(billing_email=email)
    return {'authorization_url': result['authorization_url'], 'reference': reference}


def _paid_at(data):
    return parse_datetime(data.get('paid_at') or data.get('paidAt') or '') or timezone.now()


def _check_amount(data, price):
    if data.get('currency', 'NGN') != price.currency or int(data.get('amount', 0)) < price.amount_kobo:
        raise ValidationError('The amount paid does not cover the plan.')


def confirm_checkout(*, hospital, reference):
    '''After the payer returns: ask Paystack itself whether the payment succeeded.'''
    data = paystack.verify_transaction(reference)
    if data.get('status') != 'success':
        raise ValidationError(f"Payment not completed ({data.get('gateway_response') or data.get('status')}).")
    metadata = data.get('metadata') or {}
    if str(metadata.get('hospital_id')) != str(hospital.pk):
        raise ValidationError('This payment belongs to another account.')
    price = price_for(metadata['plan'], metadata['interval'])
    _check_amount(data, price)
    _remember_customer(hospital, data)
    payment, _ = apply_payment(
        hospital=hospital, reference=reference, source=SubscriptionPayment.Source.PAYSTACK,
        plan=price.plan, interval=price.interval, amount=Decimal(data['amount']) / 100, paid_at=_paid_at(data),
    )  # fmt: skip
    return payment


def _remember_customer(hospital, data):
    customer = (data.get('customer') or {}).get('customer_code')
    if customer:
        Subscription.objects.filter(hospital=hospital).update(paystack_customer_code=customer)


def cancel_auto_renew(*, hospital):
    '''Stop renewing; access continues until the paid period ends.'''
    subscription = Subscription.objects.get(hospital=hospital)
    if subscription.paystack_subscription_code and subscription.paystack_email_token:
        paystack.disable_subscription(
            code=subscription.paystack_subscription_code, email_token=subscription.paystack_email_token
        )
    subscription.status = Subscription.Status.CANCELLED
    subscription.cancel_at_period_end = True
    subscription.save(update_fields=['status', 'cancel_at_period_end', 'updated_at'])
    record('subscription.cancelled', Category.DOMAIN, resource=subscription)
    return subscription


# ---- Webhooks (renewals, failures, cancellations) ----


def _subscription_for(data):
    metadata = data.get('metadata') or {}
    if isinstance(metadata, dict) and metadata.get('hospital_id'):
        found = Subscription.objects.filter(hospital_id=metadata['hospital_id']).select_related('hospital').first()
        if found:
            return found
    customer = (data.get('customer') or {}).get('customer_code')
    if customer:
        found = Subscription.objects.filter(paystack_customer_code=customer).select_related('hospital').first()
        if found:
            return found
    code = data.get('subscription_code') or (data.get('subscription') or {}).get('subscription_code')
    if code:
        return Subscription.objects.filter(paystack_subscription_code=code).select_related('hospital').first()
    return None


def handle_webhook(event):
    '''Apply a verified Paystack event. Unknown events and unknown customers are ignored.'''
    kind, data = event.get('event'), event.get('data') or {}
    subscription = _subscription_for(data)
    if subscription is None:
        return 'ignored: unknown customer'
    hospital = subscription.hospital

    if kind == 'charge.success':
        metadata = data.get('metadata') if isinstance(data.get('metadata'), dict) else {}
        plan_code = (data.get('plan') or {}).get('plan_code') if isinstance(data.get('plan'), dict) else None
        price = (
            PlanPrice.objects.filter(paystack_plan_code=plan_code).first()
            if plan_code
            else price_for(metadata.get('plan', hospital.plan), metadata.get('interval', subscription.interval))
        )
        if price is None:
            return 'ignored: unknown plan'
        _check_amount(data, price)
        _remember_customer(hospital, data)
        _, created = apply_payment(
            hospital=hospital, reference=data['reference'], source=SubscriptionPayment.Source.PAYSTACK,
            plan=price.plan, interval=price.interval, amount=Decimal(data['amount']) / 100, paid_at=_paid_at(data),
        )  # fmt: skip
        return 'payment applied' if created else 'payment already applied'

    if kind == 'subscription.create':
        subscription.paystack_subscription_code = data.get('subscription_code', '')
        subscription.paystack_email_token = data.get('email_token', '')
        subscription.save(update_fields=['paystack_subscription_code', 'paystack_email_token', 'updated_at'])
        return 'subscription linked'

    if kind == 'invoice.payment_failed':
        subscription.status = Subscription.Status.PAST_DUE
        subscription.save(update_fields=['status', 'updated_at'])
        record('subscription.payment_failed', Category.DOMAIN, resource=subscription)
        return 'marked past due'

    if kind in ('subscription.disable', 'subscription.not_renew'):
        subscription.status = Subscription.Status.CANCELLED
        subscription.cancel_at_period_end = True
        subscription.save(update_fields=['status', 'cancel_at_period_end', 'updated_at'])
        return 'marked cancelled'

    return f'ignored: {kind}'


def record_manual_payment(*, hospital, plan, interval, amount, reference, note, by):
    '''A platform operator records a bank transfer or other offline payment.'''
    payment, created = apply_payment(
        hospital=hospital, reference=f'manual-{reference}', source=SubscriptionPayment.Source.MANUAL,
        plan=plan, interval=interval, amount=amount, note=note, recorded_by=by.email,
    )  # fmt: skip
    if not created:
        raise ValidationError({'reference': 'A payment with this reference was already recorded.'})
    return payment


@transaction.atomic
def extend_access(*, hospital, days, reason, by):
    '''
    A platform operator gives a hospital extra days (a longer trial, or
    goodwill while a payment is sorted out). Counts from the current end, or
    from today if that has passed.
    '''
    subscription = Subscription.objects.select_for_update().filter(hospital=hospital).first() or start_trial(hospital)
    starts = max(timezone.now(), subscription.current_period_end)
    subscription.current_period_end = starts + timedelta(days=days)
    if subscription.status == Subscription.Status.PAST_DUE:
        subscription.status = Subscription.Status.ACTIVE
    subscription.save()
    record(
        'subscription.extended', Category.DOMAIN, resource=subscription,
        metadata={'days': days, 'reason': reason, 'by': by.email, 'until': subscription.current_period_end.isoformat()},
    )  # fmt: skip
    return subscription


def describe(subscription, now=None):
    '''What the hospital (and the web app's banner) needs to know.'''
    now = now or timezone.now()
    access = subscription.access(now)
    status = subscription.status
    if status in (Subscription.Status.ACTIVE, Subscription.Status.TRIALING) and now > subscription.current_period_end:
        status = Subscription.Status.PAST_DUE  # renewal time passed without a payment
    return {
        'status': status,
        'access': access,
        'interval': subscription.interval,
        'current_period_end': subscription.current_period_end,
        'grace_ends_at': subscription.grace_ends_at,
        'days_left': subscription.days_left(now),
        'cancel_at_period_end': subscription.cancel_at_period_end,
        'auto_renews': bool(subscription.paystack_subscription_code) and not subscription.cancel_at_period_end,
    }
