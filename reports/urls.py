from django.urls import path

from .views import ClinicalReportView, FinancialReportView, LabReportView, PharmacyReportView

urlpatterns = [
    path('clinical/', ClinicalReportView.as_view(), name='report-clinical'),
    path('financial/', FinancialReportView.as_view(), name='report-financial'),
    path('pharmacy/', PharmacyReportView.as_view(), name='report-pharmacy'),
    path('lab/', LabReportView.as_view(), name='report-lab'),
]
