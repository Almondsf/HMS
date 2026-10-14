from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from audit.models import AuditEvent
from authentication.models import User
from clinical.models import Visit
from helpers.testing import TenantAPITestCase, make_user
from scheduling.models import Appointment

Role = User.UserType


def today():
    '''A time today in hospital time (check-in only needs the same day; avoids midnight flakiness).'''
    return timezone.localtime().replace(second=0, microsecond=0)


class BookingTests(TenantAPITestCase):
    def setUp(self):
        self.doctor = make_user(Role.DOCTOR).doctorprofile
        self.patient = make_user(Role.PATIENT).patientprofile
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))
        self.slot = timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)

    def book(self, starts_at=None, patient=None, doctor=None, **extra):
        return self.client.post('/api/v1/appointments/', {
            'patient': (patient or self.patient).id,
            'doctor': (doctor or self.doctor).id,
            'starts_at': (starts_at or self.slot).isoformat(),
            **extra,
        })  # fmt: skip

    def test_booking(self):
        response = self.book(duration_minutes=30, reason='Follow-up')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['status'], 'scheduled')
        self.assertEqual(response.data['duration_minutes'], 30)
        self.assertEqual(response.data['patient_mrn'], self.patient.mrn)
        self.assertTrue(AuditEvent.objects.filter(action='scheduling.appointment_booked').exists())

    def test_doctor_cannot_be_double_booked(self):
        self.book(duration_minutes=30)
        other_patient = make_user(Role.PATIENT).patientprofile
        clash = self.book(self.slot + timedelta(minutes=15), patient=other_patient)
        self.assertEqual(clash.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already has an appointment', str(clash.data['starts_at']))

        back_to_back = self.book(self.slot + timedelta(minutes=30), patient=other_patient)
        self.assertEqual(back_to_back.status_code, status.HTTP_201_CREATED)

    def test_patient_cannot_be_in_two_places(self):
        self.book()
        other_doctor = make_user(Role.DOCTOR).doctorprofile
        self.assertEqual(self.book(doctor=other_doctor).status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancelled_slot_can_be_rebooked(self):
        first = self.book().data
        self.client.post(f"/api/v1/appointments/{first['id']}/cancel/", {'reason': 'Travelling'})
        self.assertEqual(self.book().status_code, status.HTTP_201_CREATED)
        self.assertEqual(Appointment.objects.get(pk=first['id']).cancellation_reason, 'Travelling')

    def test_invalid_bookings(self):
        cases = {
            'past': {'starts_at': timezone.now() - timedelta(hours=1)},
            'too long': {'duration_minutes': 600},
        }
        for name, extra in cases.items():
            with self.subTest(name):
                self.assertEqual(self.book(**extra).status_code, status.HTTP_400_BAD_REQUEST)

    def test_reschedule_checks_for_clashes(self):
        first = self.book().data
        self.book(self.slot + timedelta(hours=1), patient=make_user(Role.PATIENT).patientprofile)

        moved = self.client.patch(
            f"/api/v1/appointments/{first['id']}/", {'starts_at': (self.slot + timedelta(hours=2)).isoformat()}
        )
        self.assertEqual(moved.status_code, status.HTTP_200_OK, moved.data)
        clash = self.client.patch(
            f"/api/v1/appointments/{first['id']}/", {'starts_at': (self.slot + timedelta(hours=1)).isoformat()}
        )
        self.assertEqual(clash.status_code, status.HTTP_400_BAD_REQUEST)
        change_doctor = self.client.patch(
            f"/api/v1/appointments/{first['id']}/", {'doctor': make_user(Role.DOCTOR).doctorprofile.id}
        )
        self.assertEqual(change_doctor.status_code, status.HTTP_400_BAD_REQUEST)

    def test_who_sees_and_books_appointments(self):
        mine = self.book().data
        self.book(patient=make_user(Role.PATIENT).patientprofile, doctor=make_user(Role.DOCTOR).doctorprofile)

        self.client.force_authenticate(self.doctor.user)
        self.assertEqual([a['id'] for a in self.client.get('/api/v1/appointments/').data['results']], [mine['id']])
        self.assertEqual(self.book(self.slot + timedelta(days=1)).status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.patient.user)
        self.assertEqual([a['id'] for a in self.client.get('/api/v1/appointments/').data['results']], [mine['id']])

    def test_filter_by_day(self):
        tomorrow = self.book().data
        self.book(self.slot + timedelta(days=1))
        response = self.client.get('/api/v1/appointments/', {'date': timezone.localdate(self.slot).isoformat()})
        self.assertEqual([a['id'] for a in response.data['results']], [tomorrow['id']])


class CheckInAndQueueTests(TenantAPITestCase):
    def setUp(self):
        self.doctor = make_user(Role.DOCTOR).doctorprofile
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))

    def appointment(self, starts_at, patient=None):
        return Appointment.objects.create(
            patient=patient or make_user(Role.PATIENT).patientprofile,
            doctor=self.doctor,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=15),
            reason='Review',
        )

    def walk_in(self):
        response = self.client.post('/api/v1/visits/', {
            'patient': make_user(Role.PATIENT).patientprofile.id,
            'assigned_doctor': self.doctor.id,
            'reason_for_visit': 'Walk-in',
        })  # fmt: skip
        return Visit.objects.get(pk=response.data['id'])

    def test_check_in_puts_the_patient_in_the_queue(self):
        appointment = self.appointment(today())
        response = self.client.post(f'/api/v1/appointments/{appointment.id}/check-in/')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'checked_in')
        visit = Visit.objects.get(pk=response.data['visit'])
        self.assertEqual((visit.status, visit.assigned_doctor), (Visit.Status.WAITING, self.doctor))

        [entry] = self.client.get('/api/v1/queue/').data
        self.assertEqual((entry['id'], entry['position']), (visit.id, 1))
        self.assertIsNotNone(entry['appointment_time'])

        again = self.client.post(f'/api/v1/appointments/{appointment.id}/check-in/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_in_only_on_the_day(self):
        appointment = self.appointment(timezone.now() + timedelta(days=2))
        response = self.client.post(f'/api/v1/appointments/{appointment.id}/check-in/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_show_only_after_start(self):
        upcoming = self.appointment(timezone.now() + timedelta(hours=2))
        self.assertEqual(self.client.post(f'/api/v1/appointments/{upcoming.id}/no-show/').status_code, 400)
        missed = self.appointment(timezone.now() - timedelta(minutes=30))
        response = self.client.post(f'/api/v1/appointments/{missed.id}/no-show/')
        self.assertEqual(response.data['status'], 'no_show')

    def test_queue_order_positions_and_doctor_view(self):
        first, second, third = self.walk_in(), self.walk_in(), self.walk_in()
        other_doctors_patient = self.client.post('/api/v1/visits/', {
            'patient': make_user(Role.PATIENT).patientprofile.id,
            'assigned_doctor': make_user(Role.DOCTOR).doctorprofile.id,
            'reason_for_visit': 'Elsewhere',
        })  # fmt: skip
        self.assertEqual(other_doctors_patient.status_code, 201)

        self.client.force_authenticate(self.doctor.user)
        self.client.post(f'/api/v1/visits/{second.id}/start/')
        queue = self.client.get('/api/v1/queue/').data

        # In the room first (no position), then the waiting line in arrival order
        self.assertEqual([(e['id'], e['position']) for e in queue], [(second.id, None), (first.id, 1), (third.id, 2)])
        self.assertEqual(queue[1]['patient']['mrn'], first.patient.mrn)

        self.client.post(f'/api/v1/visits/{second.id}/complete/')
        self.assertEqual([e['id'] for e in self.client.get('/api/v1/queue/').data], [first.id, third.id])

    def test_visit_transitions(self):
        visit = self.walk_in()
        # Front desk can't start consultations; doctors can't start other doctors' visits
        self.assertEqual(self.client.post(f'/api/v1/visits/{visit.id}/start/').status_code, 403)
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.client.post(f'/api/v1/visits/{visit.id}/start/').status_code, 404)

        self.client.force_authenticate(self.doctor.user)
        self.assertEqual(self.client.post(f'/api/v1/visits/{visit.id}/start/').data['status'], 'in_progress')
        self.assertEqual(self.client.post(f'/api/v1/visits/{visit.id}/start/').status_code, 400)

        self.client.force_authenticate(make_user(Role.RECEPTIONIST))
        self.assertEqual(self.client.post(f'/api/v1/visits/{visit.id}/cancel/').status_code, 400)  # already seen
        self.assertEqual(
            self.client.patch(f'/api/v1/visits/{visit.id}/', {'status': 'cancelled'}).data['status'], 'in_progress'
        )

    def test_recording_a_consultation_starts_the_visit(self):
        visit = self.walk_in()
        self.client.force_authenticate(self.doctor.user)
        self.client.post('/api/v1/consultations/', {'visit': visit.id, 'assessment': 'URTI'}, format='json')
        visit.refresh_from_db()
        self.assertEqual(visit.status, Visit.Status.IN_PROGRESS)
