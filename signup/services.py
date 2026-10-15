'''
Self-serve signup: a hospital owner signs up, verifies their email, and the
hospital is created for them on a free trial.

Creating a hospital takes 30+ seconds (a schema with every table), longer than
a web request may run, so it happens in a background thread after the email
is verified; the web app polls for the result. A deploy can interrupt that
thread: `manage.py process_signups` finishes any interrupted setup.
'''

import hashlib
import logging
import re
import secrets
import threading
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import connections, transaction
from django.utils import timezone

from audit.recorder import Category, record
from authentication.models import User
from tenants.models import Hospital
from tenants.services import default_domain, provision_hospital, validate_new_hospital

from .models import Signup

logger = logging.getLogger('hms.signup')

LINK_VALID_FOR = timedelta(hours=48)
SIGNUPS_PER_EMAIL_PER_DAY = 3
STALLED_AFTER = timedelta(minutes=15)

ADDRESS = re.compile(r'^[a-z][a-z0-9-]{1,38}[a-z0-9]$')
# Addresses that could pass for the platform itself, or that we may want later
RESERVED_ADDRESSES = {
    'account', 'accounts', 'admin', 'api', 'app', 'assets', 'auth', 'billing', 'blog', 'cdn', 'dashboard',
    'demo', 'dev', 'docs', 'email', 'ftp', 'help', 'hms', 'login', 'mail', 'media', 'ns1', 'ns2', 'platform',
    'public', 'root', 'signup', 'smtp', 'staging', 'static', 'status', 'support', 'template', 'test', 'www',
}  # fmt: skip


class EmailNotSent(Exception):
    pass


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def schema_for(address):
    return address.replace('-', '_')


def address_problem(address):
    '''Why this hospital address can't be used, or None if it's free.'''
    if not ADDRESS.match(address) or '--' in address:
        return 'Use 3-40 lowercase letters, digits or hyphens, starting with a letter.'
    if address in RESERVED_ADDRESSES:
        return 'This address is reserved. Please choose another.'
    schema = schema_for(address)
    try:
        validate_new_hospital(schema_name=schema, domain=default_domain(schema))
    except ValidationError:
        return 'This address is already taken.'
    return None


def request_signup(*, hospital_name, address, plan, first_name, last_name, email, phone, password, ip, verify_url):
    '''
    Check the details and email a verification link. `verify_url(token)`
    builds the link. Repeated signups for one email are quietly capped.
    '''
    problem = address_problem(address)
    if problem:
        raise ValidationError({'address': problem})
    try:
        validate_password(password, user=User(email=email, first_name=first_name, last_name=last_name))
    except ValidationError as exc:
        raise ValidationError({'password': exc.messages}) from exc

    since = timezone.now() - timedelta(days=1)
    if Signup.objects.filter(email__iexact=email, created_at__gte=since).count() >= SIGNUPS_PER_EMAIL_PER_DAY:
        # Same answer as success, so the form can't be used to spam someone's inbox
        record('signup.capped', Category.SECURITY, metadata={'email': email, 'address': address})
        return None

    token = secrets.token_urlsafe(32)
    signup = Signup.objects.create(
        hospital_name=hospital_name, address=address, plan=plan, first_name=first_name, last_name=last_name,
        email=email, phone=phone, password_hash=make_password(password), token_hash=_hash(token), ip=ip,
    )  # fmt: skip
    try:
        send_mail(
            subject=f'Confirm your email to set up {hospital_name}',
            message=(
                f'Hello {first_name},\n\n'
                f'Thanks for signing up {hospital_name}. Confirm your email address to create your hospital '
                f'(the link works for {LINK_VALID_FOR.days * 24} hours):\n\n'
                f'{verify_url(token)}\n\n'
                "If you didn't sign up, ignore this email and nothing will be created.\n\n"
                f'The {settings.PRODUCT_NAME} team'
            ),
            from_email=None,
            recipient_list=[email],
        )
    except Exception as exc:
        signup.delete()
        logger.exception('Could not send the signup verification email')
        raise EmailNotSent from exc
    record('signup.requested', Category.SECURITY, resource=signup, metadata={'address': address, 'plan': plan})
    return signup


def find(token):
    return Signup.objects.filter(token_hash=_hash(token)).first() if token else None


def verify(*, token, login_url):
    '''
    Confirm the email and start creating the hospital. Clicking the link
    again is harmless: it just reports progress.
    '''
    with transaction.atomic():
        signup = Signup.objects.select_for_update().filter(token_hash=_hash(token)).first()
        if signup is None:
            raise ValidationError({'token': 'This link is not valid. Check that you copied all of it.'})
        if signup.status != Signup.Status.PENDING:
            return signup
        if signup.created_at < timezone.now() - LINK_VALID_FOR:
            raise ValidationError({'token': 'This link has expired. Please sign up again.'})
        now = timezone.now()
        signup.status = Signup.Status.PROVISIONING
        signup.verified_at = signup.provisioning_started_at = now
        signup.login_url = login_url
        signup.save()
        record('signup.verified', Category.SECURITY, resource=signup)
        transaction.on_commit(lambda: start_provisioning(signup.pk))
    return signup


def start_provisioning(signup_id):
    if not settings.SIGNUP_PROVISION_IN_BACKGROUND:
        provision(signup_id)
        return
    # Not a daemon: a graceful shutdown waits for the setup to finish
    threading.Thread(target=_provision_in_thread, args=(signup_id,), name=f'signup-{signup_id}').start()


def _provision_in_thread(signup_id):
    try:
        provision(signup_id)
    finally:
        connections.close_all()  # this thread's own database connection


def _failure_message(exc):
    if (
        isinstance(exc, ValidationError)
        and hasattr(exc, 'error_dict')
        and exc.error_dict.keys() & {'schema_name', 'domain'}
    ):
        return 'This address was taken while your hospital was being set up. Please sign up again with another.'
    return 'Something went wrong while setting up your hospital. Our team has been told and will contact you.'


def provision(signup_id):
    '''Create the hospital for a verified signup. Safe to call again.'''
    signup = Signup.objects.get(pk=signup_id)
    if signup.status == Signup.Status.READY:
        return signup
    schema = schema_for(signup.address)
    try:
        hospital, _ = provision_hospital(
            name=signup.hospital_name, schema_name=schema, plan=signup.plan, contact_email=signup.email,
            admin_email=signup.email, admin_password_hash=signup.password_hash,
            admin_first_name=signup.first_name, admin_last_name=signup.last_name,
        )  # fmt: skip
    except Exception as exc:
        logger.exception('Setting up hospital %s for signup %s failed', schema, signup.pk)
        signup.status, signup.error = Signup.Status.FAILED, _failure_message(exc)
        signup.save(update_fields=['status', 'error', 'updated_at'])
        record('signup.failed', Category.DOMAIN, resource=signup, metadata={'error': str(exc)[:500]})
        return signup

    if signup.phone:
        Hospital.objects.filter(pk=hospital.pk).update(phone=signup.phone)
    signup.status, signup.hospital, signup.error = Signup.Status.READY, hospital, ''
    signup.password_hash = ''  # the admin account has it now
    signup.completed_at = timezone.now()
    signup.save()
    record('signup.completed', Category.DOMAIN, resource=signup, metadata={'hospital_id': hospital.pk})
    try:
        send_mail(
            subject=f'{signup.hospital_name} is ready',
            message=(
                f'Hello {signup.first_name},\n\n'
                f'{signup.hospital_name} is set up, with a {settings.SUBSCRIPTION_TRIAL_DAYS}-day free trial '
                f'of the {signup.plan.title()} plan.\n\n'
                f'Your hospital\'s address: {signup.login_url}\n'
                f'Sign in with {signup.email} and the password you chose.\n\n'
                'Next steps: add your staff (Staff), set your prices (Fees) and check your settings.\n\n'
                f'The {settings.PRODUCT_NAME} team'
            ),
            from_email=None,
            recipient_list=[signup.email],
        )
    except Exception:
        logger.exception('Could not send the welcome email for signup %s', signup.pk)
    return signup


def stalled():
    '''Setups interrupted part-way (e.g. by a deploy).'''
    return Signup.objects.filter(
        status=Signup.Status.PROVISIONING, provisioning_started_at__lt=timezone.now() - STALLED_AFTER
    )


def purge_unverified(older_than=timedelta(days=7)):
    '''Unverified signups hold personal details and a password hash: don't keep them.'''
    cutoff = timezone.now() - older_than
    deleted, _ = Signup.objects.filter(status=Signup.Status.PENDING, created_at__lt=cutoff).delete()
    Signup.objects.filter(status=Signup.Status.FAILED, updated_at__lt=cutoff).exclude(password_hash='').update(
        password_hash=''
    )
    return deleted


def describe(signup):
    data = {'status': signup.status, 'hospital_name': signup.hospital_name, 'address': signup.address}
    if signup.status == Signup.Status.READY:
        data['login_url'] = signup.login_url
        data['email'] = signup.email
    if signup.status == Signup.Status.FAILED:
        data['error'] = signup.error
    if signup.status == Signup.Status.PROVISIONING:
        data['stalled'] = signup.provisioning_started_at < timezone.now() - STALLED_AFTER
    return data
