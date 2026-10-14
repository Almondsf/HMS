from itertools import count

from django.db import connection
from django_tenants.test.cases import FastTenantTestCase
from rest_framework.test import APIClient

from authentication.models import User
from profiles.models import (
    CashierProfile,
    DoctorProfile,
    LabTechProfile,
    NurseProfile,
    PatientProfile,
    PharmacistProfile,
    ReceptionistProfile,
)

PROFILE_MODELS = {
    User.UserType.DOCTOR: DoctorProfile,
    User.UserType.PATIENT: PatientProfile,
    User.UserType.LAB_TECHNICIAN: LabTechProfile,
    User.UserType.PHARMACIST: PharmacistProfile,
    User.UserType.RECEPTIONIST: ReceptionistProfile,
    User.UserType.CASHIER: CashierProfile,
    User.UserType.NURSE: NurseProfile,
}

TEST_PASSWORD = 'Str0ng-pass!'

_ids = count(1)


def make_user(user_type, **profile_fields):
    '''Create a user of the given role, plus its profile when the role has one.'''
    n = next(_ids)
    user = User.objects.create_user(
        first_name='Test',
        last_name=f'{user_type}{n}',
        email=f'{user_type}{n}@example.com',
        password=TEST_PASSWORD,
        user_type=user_type,
    )
    profile_model = PROFILE_MODELS.get(user_type)
    if profile_model:
        if user_type == User.UserType.DOCTOR:
            profile_fields.setdefault('specialty', 'General')
        if user_type == User.UserType.PATIENT:
            profile_fields.setdefault('mrn', f'TEST-{n:06d}')
        profile_model.objects.create(user=user, **profile_fields)
    return user


def make_consultation(doctor=None, patient=None):
    '''A consultation on a fresh visit between the given (or new) doctor and patient.'''
    from clinical.models import Consultation, Visit

    doctor = doctor or make_user(User.UserType.DOCTOR)
    patient = patient or make_user(User.UserType.PATIENT)
    visit = Visit.objects.create(
        patient=patient.patientprofile, assigned_doctor=doctor.doctorprofile, reason_for_visit='Checkup'
    )
    return Consultation.objects.create(visit=visit)


TEST_HOSPITAL_DOMAIN = 'test-hospital.localhost'


class SchemaRestoringAPIClient(APIClient):
    '''
    The hospital middleware leaves the connection on the requested hospital's
    schema (each real request sets it afresh). In tests the connection is
    shared with the test body, so restore the caller's schema afterwards.
    '''

    def request(self, **kwargs):
        previous = connection.tenant
        try:
            return super().request(**kwargs)
        finally:
            connection.set_tenant(previous)


class TenantAPIClient(SchemaRestoringAPIClient):
    '''API client whose requests go to the test hospital's address.'''

    def __init__(self, **defaults):
        super().__init__(HTTP_HOST=TEST_HOSPITAL_DOMAIN, **defaults)


class TenantAPITestCase(FastTenantTestCase):
    '''
    API tests inside a hospital. The test hospital's schema is created once
    per run; each test runs in a transaction that is rolled back.
    '''

    client_class = TenantAPIClient

    @classmethod
    def get_test_schema_name(cls):
        return 'test_hospital'

    @classmethod
    def get_test_tenant_domain(cls):
        return TEST_HOSPITAL_DOMAIN

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Test Hospital'
        tenant.plan = 'enterprise'  # every module enabled; plan gating has its own tests

    @classmethod
    def _fixture_setup(cls):
        # Every test starts inside the test hospital, whatever the last one did
        connection.set_tenant(cls.tenant)
        super()._fixture_setup()
