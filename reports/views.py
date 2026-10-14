from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import Role, allow_roles
from helpers.api import parse_date_param
from tenants.features import Feature, requires_feature

from . import services

MAX_DAYS = 366


def _period(params):
    '''date_from / date_to (YYYY-MM-DD), default the last 30 days, at most a year.'''
    default_from, default_to = services.default_period()
    parsed = {
        'date_from': parse_date_param(params, 'date_from', default_from),
        'date_to': parse_date_param(params, 'date_to', default_to),
    }
    if parsed['date_from'] > parsed['date_to']:
        raise ValidationError({'date_from': 'Must be on or before date_to.'})
    if (parsed['date_to'] - parsed['date_from']).days >= MAX_DAYS:
        raise ValidationError({'date_from': f'Reports cover at most {MAX_DAYS} days.'})
    return parsed['date_from'], parsed['date_to']


class ReportView(APIView):
    report = None

    def get(self, request):
        return Response(self.report(*_period(request.query_params)))


class ClinicalReportView(ReportView):
    '''Visits per day and doctor, waiting and consultation times, new patients, top diagnoses.'''

    report = staticmethod(services.clinical_report)
    permission_classes = [requires_feature(Feature.CLINICAL), allow_roles(read=[Role.ADMIN])]


class FinancialReportView(ReportView):
    '''Money collected and charged, receivables with aging, insurer balances.'''

    report = staticmethod(services.financial_report)
    permission_classes = [requires_feature(Feature.BILLING), allow_roles(read=[Role.ADMIN, Role.CASHIER])]


class PharmacyReportView(ReportView):
    '''Most dispensed drugs, low stock, stock value.'''

    report = staticmethod(services.pharmacy_report)
    permission_classes = [requires_feature(Feature.PHARMACY), allow_roles(read=[Role.ADMIN, Role.PHARMACIST])]


class LabReportView(ReportView):
    '''Test volumes, turnaround time, pending work.'''

    report = staticmethod(services.lab_report)
    permission_classes = [requires_feature(Feature.LAB), allow_roles(read=[Role.ADMIN, Role.LAB_TECHNICIAN])]
