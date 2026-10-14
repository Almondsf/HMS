from datetime import timedelta
from decimal import Decimal

from django.db import migrations
from django.utils import timezone

# Placeholder prices in naira: set real ones in the platform admin before charging anyone.
# Yearly = 10 x monthly (two months free).
MONTHLY = {'basic': Decimal('25000'), 'pro': Decimal('60000'), 'enterprise': Decimal('150000')}


def seed(apps, schema_editor):
    PlanPrice = apps.get_model('subscriptions', 'PlanPrice')
    Subscription = apps.get_model('subscriptions', 'Subscription')
    Hospital = apps.get_model('tenants', 'Hospital')

    for plan, monthly in MONTHLY.items():
        PlanPrice.objects.get_or_create(plan=plan, interval='monthly', defaults={'amount': monthly})
        PlanPrice.objects.get_or_create(plan=plan, interval='yearly', defaults={'amount': monthly * 10})

    # Hospitals that existed before subscriptions: 30 days to sort out payment
    ends = timezone.now() + timedelta(days=30)
    for hospital in Hospital.objects.exclude(schema_name='public'):
        Subscription.objects.get_or_create(
            hospital=hospital,
            defaults={'status': 'trialing', 'current_period_end': ends, 'billing_email': hospital.contact_email},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('subscriptions', '0001_initial'),
        ('tenants', '0002_hospital_settings'),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
