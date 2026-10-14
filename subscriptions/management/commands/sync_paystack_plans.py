from django.core.management.base import BaseCommand, CommandError

from subscriptions import paystack
from subscriptions.models import PlanPrice


class Command(BaseCommand):
    help = (
        'Create a Paystack plan for every active price that lacks one (needed for automatic renewals). '
        'Paystack plans have a fixed amount: after changing a price, run with --reprice to create a new '
        'plan for it (existing subscribers keep renewing at their old plan until they re-subscribe).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--reprice', action='store_true', help='Create new plans even where a code exists')

    def handle(self, *args, reprice, **options):
        prices = PlanPrice.objects.filter(is_active=True)
        if not reprice:
            prices = prices.filter(paystack_plan_code='')
        for price in prices:
            try:
                plan = paystack.create_plan(
                    name=f'HMS {price.plan.title()} ({price.interval}, {price.currency} {price.amount:,.0f})',
                    interval=price.interval,
                    amount_kobo=price.amount_kobo,
                    currency=price.currency,
                )
            except paystack.PaystackError as exc:
                raise CommandError(f'{price}: {exc}') from exc
            price.paystack_plan_code = plan['plan_code']
            price.save(update_fields=['paystack_plan_code', 'updated_at'])
            self.stdout.write(f'  {price}: {price.paystack_plan_code}')
        self.stdout.write(self.style.SUCCESS('Paystack plans are in sync.'))
