from django.db import connection
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.mixins import AuditedReadMixin
from authentication.permissions import STAFF_ROLES, Role, allow_roles
from helpers.api import parse_date_param
from tenants.features import Feature, requires_feature

from . import services
from .filters import InvoiceFilter, PaymentFilter
from .models import Invoice, Payment, ServiceItem
from .serializers import (
    DiscountSerializer,
    InvoiceLineSerializer,
    InvoiceSerializer,
    ManualLineSerializer,
    PaymentSerializer,
    PriceSerializer,
    ReasonSerializer,
    ServiceItemSerializer,
)

BILLING = requires_feature(Feature.BILLING)
CASHIERS = [Role.CASHIER, Role.ADMIN]
MANAGERS_ONLY = [BILLING, allow_roles(write=[Role.ADMIN])]
CASHIERS_ONLY = [BILLING, allow_roles(write=CASHIERS)]


def _validated(serializer_class, request):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class ServiceItemViewSet(viewsets.ModelViewSet):
    '''The hospital's tariff. Admins set prices and which fees are charged automatically.'''

    queryset = ServiceItem.objects.all()
    serializer_class = ServiceItemSerializer
    filterset_fields = ['category', 'charge_on', 'is_active']
    permission_classes = [BILLING, allow_roles(read=STAFF_ROLES, write=[Role.ADMIN])]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


class InvoiceViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''
    Patient invoices. Charges arrive automatically from visits, consultations,
    lab orders and dispensing; cashiers add others, set missing prices and issue
    the bill. Filters: patient, visit, status, outstanding=true, date_from, date_to.
    '''

    serializer_class = InvoiceSerializer
    filterset_class = InvoiceFilter
    ordering_fields = ['created_at', 'issued_at']
    permission_classes = [BILLING, allow_roles(read=[Role.RECEPTIONIST, Role.PATIENT], write=CASHIERS)]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        invoices = (
            Invoice.objects.with_totals()
            .select_related('patient__user')
            .prefetch_related('lines__added_by', 'payments__received_by')
        )
        if self.request.user.user_type == Role.PATIENT:
            return invoices.filter(patient__user=self.request.user)
        return invoices

    def _respond(self, invoice):
        return Response(self.get_serializer(self.get_queryset().get(pk=invoice.pk)).data)

    @action(detail=True, methods=['post'], permission_classes=CASHIERS_ONLY)
    def lines(self, request, pk=None):
        '''Add a charge: a tariff `service_item`, or a `description` with a `unit_price`.'''
        services.add_manual_line(
            invoice=self.get_object(), by=request.user, **_validated(ManualLineSerializer, request)
        )
        return self._respond(self.get_object())

    @action(detail=True, methods=['post'], url_path=r'lines/(?P<line_id>\d+)/price', permission_classes=CASHIERS_ONLY)
    def price_line(self, request, pk=None, line_id=None):
        invoice = self.get_object()
        line = get_object_or_404(invoice.lines, pk=line_id)
        services.price_line(line=line, **_validated(PriceSerializer, request))
        return self._respond(invoice)

    @action(detail=True, methods=['post'], url_path=r'lines/(?P<line_id>\d+)/void', permission_classes=CASHIERS_ONLY)
    def void_line(self, request, pk=None, line_id=None):
        invoice = self.get_object()
        line = get_object_or_404(invoice.lines, pk=line_id)
        services.void_line(line=line, **_validated(ReasonSerializer, request))
        return self._respond(invoice)

    @action(detail=True, methods=['post'], permission_classes=MANAGERS_ONLY)
    def discount(self, request, pk=None):
        return self._respond(
            services.apply_discount(invoice=self.get_object(), **_validated(DiscountSerializer, request))
        )

    @action(detail=True, methods=['post'], permission_classes=CASHIERS_ONLY)
    def issue(self, request, pk=None):
        return self._respond(services.issue_invoice(invoice=self.get_object()))

    @action(detail=True, methods=['post'], permission_classes=MANAGERS_ONLY)
    def void(self, request, pk=None):
        return self._respond(services.void_invoice(invoice=self.get_object(), **_validated(ReasonSerializer, request)))


class PaymentViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''
    Payments against invoices. Never more than the balance due. Voiding (admin)
    reverses a payment recorded in error. Filters: invoice, method,
    received_by, date_from, date_to.
    '''

    serializer_class = PaymentSerializer
    filterset_class = PaymentFilter
    ordering_fields = ['created_at', 'amount']
    permission_classes = [BILLING, allow_roles(read=[Role.PATIENT], write=[*CASHIERS, Role.RECEPTIONIST])]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        payments = Payment.objects.select_related('invoice__patient__user', 'received_by')
        if self.request.user.user_type == Role.PATIENT:
            return payments.filter(invoice__patient__user=self.request.user)
        return payments

    @action(detail=True, methods=['post'], permission_classes=MANAGERS_ONLY)
    def void(self, request, pk=None):
        payment = services.void_payment(payment=self.get_object(), **_validated(ReasonSerializer, request))
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        '''Everything needed to print a receipt.'''
        payment = self.get_object()
        invoice = Invoice.objects.with_totals().get(pk=payment.invoice_id)
        hospital = connection.tenant
        return Response({
            'hospital': {
                'name': hospital.name, 'address': hospital.address,
                'phone': hospital.phone, 'email': hospital.contact_email,
            },
            'receipt_number': payment.receipt_number,
            'date': timezone.localtime(payment.created_at),
            'patient': {'name': invoice.patient.user.get_full_name(), 'mrn': invoice.patient.mrn},
            'invoice_number': invoice.number,
            'currency': hospital.currency,
            'lines': InvoiceLineSerializer(invoice.lines.filter(voided=False), many=True).data,
            'invoice_total': invoice.total,
            'amount_paid_now': payment.amount,
            'method': payment.get_method_display(),
            'reference': payment.reference,
            'balance_after': invoice.balance,
            'received_by': payment.received_by.get_full_name() if payment.received_by else None,
            'voided': payment.voided,
        })  # fmt: skip


class DailySummaryView(APIView):
    '''End-of-day reconciliation: ?date=YYYY-MM-DD (default today, hospital time).'''

    permission_classes = [BILLING, allow_roles(read=CASHIERS)]

    def get(self, request):
        day = parse_date_param(request.query_params, 'date', timezone.localdate())
        return Response(services.daily_summary(day), status=status.HTTP_200_OK)
