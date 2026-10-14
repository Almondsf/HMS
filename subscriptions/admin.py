from django.contrib import admin
from django.db import connection
from django_tenants.utils import get_public_schema_name

from tenants.admin import PlatformOnlyAdmin

from .models import PlanPrice, Subscription, SubscriptionPayment


def on_platform(request):
    return connection.schema_name == get_public_schema_name() and request.user.is_superuser


@admin.register(PlanPrice)
class PlanPriceAdmin(PlatformOnlyAdmin):
    '''Prices are edited here. After changing one, run `manage.py sync_paystack_plans --reprice`.'''

    list_display = ['plan', 'interval', 'amount', 'currency', 'paystack_plan_code', 'is_active']
    list_filter = ['plan', 'interval', 'is_active']

    def has_add_permission(self, request):
        return on_platform(request)


@admin.register(Subscription)
class SubscriptionAdmin(PlatformOnlyAdmin):
    list_display = ['hospital', 'status', 'interval', 'current_period_end', 'cancel_at_period_end']
    list_filter = ['status', 'interval']
    search_fields = ['hospital__name', 'hospital__schema_name', 'billing_email']
    readonly_fields = ['paystack_customer_code', 'paystack_subscription_code', 'paystack_email_token']


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(PlatformOnlyAdmin):
    '''Read-only: payments are recorded through Paystack or the platform API.'''

    list_display = ['paid_at', 'hospital', 'amount', 'currency', 'plan', 'interval', 'source', 'reference']
    list_filter = ['source', 'plan', 'interval']
    search_fields = ['reference', 'hospital__name']

    def has_change_permission(self, request, obj=None):
        return False
