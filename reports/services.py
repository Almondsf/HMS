'''
Management reports. Every figure is aggregated in the database; dates are
in the hospital's own timezone (TruncDate / __date use the active timezone).
'''

from datetime import timedelta

from django.db.models import Avg, Count, DecimalField, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from billing.models import ZERO, Invoice, InvoiceLine, Payment
from clinical.models import Diagnosis, Visit
from lab.models import TestResult
from pharmacy.models import DispensedItem, Drug
from profiles.models import PatientProfile
from tenants.features import Feature, has_feature
from terminology.models import Icd10Code

AGING_BUCKETS = [(0, 30), (31, 60), (61, 90), (91, None)]


def _minutes(duration):
    return round(duration.total_seconds() / 60, 1) if duration is not None else None


def _average_duration(queryset, end, start):
    expression = ExpressionWrapper(F(end) - F(start), output_field=DurationField())
    return queryset.aggregate(average=Avg(expression))['average']


def clinical_report(date_from, date_to):
    visits = Visit.objects.filter(visit_date__date__range=(date_from, date_to))
    seen = visits.filter(started_at__isnull=False)

    per_doctor = [
        {
            'doctor_id': row['assigned_doctor_id'],
            'doctor': f"{row['assigned_doctor__user__first_name']} {row['assigned_doctor__user__last_name']}",
            'visits': row['visits'],
            'completed': row['completed'],
        }
        for row in visits.values(
            'assigned_doctor_id', 'assigned_doctor__user__first_name', 'assigned_doctor__user__last_name'
        )
        .annotate(visits=Count('id'), completed=Count('id', filter=Q(status=Visit.Status.COMPLETED)))
        .order_by('-visits')
    ]

    diagnoses = Diagnosis.objects.filter(created_at__date__range=(date_from, date_to)).exclude(
        certainty=Diagnosis.Certainty.RULED_OUT
    )
    top_codes = list(
        diagnoses.filter(code__isnull=False).values('code_id').annotate(count=Count('id')).order_by('-count')[:10]
    )
    titles = dict(Icd10Code.objects.filter(code__in=[row['code_id'] for row in top_codes]).values_list('code', 'title'))

    return {
        'period': {'from': date_from, 'to': date_to},
        'visits': {
            'total': visits.count(),
            'by_status': dict(visits.values_list('status').annotate(count=Count('id'))),
            'by_triage': dict(visits.exclude(triage_level='').values_list('triage_level').annotate(count=Count('id'))),
            'per_day': list(
                visits.annotate(day=TruncDate('visit_date')).values('day').annotate(visits=Count('id')).order_by('day')
            ),
            'per_doctor': per_doctor,
            'average_wait_minutes': _minutes(_average_duration(seen, 'started_at', 'visit_date')),
            'average_consultation_minutes': _minutes(
                _average_duration(seen.filter(completed_at__isnull=False), 'completed_at', 'started_at')
            ),
        },
        'new_patients': PatientProfile.objects.filter(user__date_joined__date__range=(date_from, date_to)).count(),
        'top_diagnoses': [
            {'code': row['code_id'], 'title': titles.get(row['code_id'], ''), 'count': row['count']}
            for row in top_codes
        ],
        'uncoded_diagnoses': diagnoses.filter(code__isnull=True).count(),
    }


def financial_report(date_from, date_to):
    payments = Payment.objects.filter(voided=False, created_at__date__range=(date_from, date_to))
    patient_payments = payments.exclude(method=Payment.Method.INSURANCE)
    charges = InvoiceLine.objects.filter(voided=False, created_at__date__range=(date_from, date_to))

    receivables = {'patients': ZERO, 'insurers': ZERO, 'invoices': 0}
    aging = {f"{low}-{high}" if high else f"{low}+": ZERO for low, high in AGING_BUCKETS}
    today = timezone.localdate()
    for invoice in Invoice.objects.filter(status=Invoice.Status.ISSUED).with_totals():
        receivables['invoices'] += 1
        receivables['patients'] += invoice.patient_due
        receivables['insurers'] += invoice.pending_insurance
        age = (today - timezone.localdate(invoice.issued_at)).days
        for low, high in AGING_BUCKETS:
            if age >= low and (high is None or age <= high):
                aging[f"{low}-{high}" if high else f"{low}+"] += invoice.balance
                break

    report = {
        'period': {'from': date_from, 'to': date_to},
        'collected': {
            'total': payments.aggregate(total=Sum('amount'))['total'] or ZERO,
            'from_patients': patient_payments.aggregate(total=Sum('amount'))['total'] or ZERO,
            'from_insurers': payments.filter(method=Payment.Method.INSURANCE).aggregate(total=Sum('amount'))['total']
            or ZERO,
            'by_method': dict(payments.values_list('method').annotate(total=Sum('amount'))),
            'per_day': list(
                payments.annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(total=Sum('amount'))
                .order_by('day')
            ),
        },
        'charged': {
            'total': charges.aggregate(total=Sum('amount'))['total'] or ZERO,
            'by_category': dict(charges.values_list('category').annotate(total=Sum('amount'))),
        },
        'receivables': {**receivables, 'aging_days': aging},
    }
    if has_feature(Feature.INSURANCE):
        from insurance.services import outstanding_by_provider

        report['insurance_outstanding'] = outstanding_by_provider()
    return report


def pharmacy_report(date_from, date_to):
    dispensed = DispensedItem.objects.filter(created_at__date__range=(date_from, date_to))
    value = ExpressionWrapper(
        F('quantity_in_stock') * F('unit_price'), output_field=DecimalField(max_digits=14, decimal_places=2)
    )
    return {
        'period': {'from': date_from, 'to': date_to},
        'top_dispensed': list(
            dispensed.values('drug_id', 'drug__name')
            .annotate(quantity=Sum('quantity_dispensed'), times=Count('id'))
            .order_by('-quantity')[:20]
        ),
        'low_stock': list(
            Drug.objects.filter(quantity_in_stock__lte=F('reorder_level'))
            .values('id', 'name', 'quantity_in_stock', 'reorder_level')
            .order_by('quantity_in_stock')
        ),
        'stock_value': Drug.objects.filter(unit_price__isnull=False).aggregate(total=Sum(value))['total'] or ZERO,
        'drugs_without_price': Drug.objects.filter(unit_price__isnull=True).count(),
    }


def lab_report(date_from, date_to):
    results = TestResult.objects.filter(order__ordered_at__date__range=(date_from, date_to))
    completed = results.filter(status=TestResult.Status.COMPLETED, completed_at__isnull=False)
    turnaround = _average_duration(completed, 'completed_at', 'order__ordered_at')
    return {
        'period': {'from': date_from, 'to': date_to},
        'tests': results.count(),
        'by_status': dict(results.values_list('status').annotate(count=Count('id'))),
        'by_test': list(
            results.values('test__name')
            .annotate(count=Count('id'), completed=Count('id', filter=Q(status=TestResult.Status.COMPLETED)))
            .order_by('-count')
        ),
        'average_turnaround_hours': round(turnaround.total_seconds() / 3600, 1) if turnaround else None,
        'pending_now': TestResult.objects.exclude(status__in=TestResult.FINAL_STATUSES).count(),
    }


def default_period():
    today = timezone.localdate()
    return today - timedelta(days=29), today
