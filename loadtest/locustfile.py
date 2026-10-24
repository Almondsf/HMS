'''
Load test: simulated hospital staff doing what they really do, mostly
leaving screens open that refresh themselves, plus searching and opening records.

Run it against a STAGING copy (never production: it signs in as real accounts
and adds load), with demo data loaded (seed_demo) and generous per-user rate limits:

    pip install -r loadtest/requirements.txt
    locust -f loadtest/locustfile.py --host https://main.staging.yourdomain.com

then open http://localhost:8089, choose the number of staff (users) and ramp-up,
and watch requests per second, response times and failures. One simulated user
is one staff member with the app open.

Settings (environment variables):
  LOADTEST_PASSWORD   password of the demo accounts (default: the seed_demo password)
  LOADTEST_HOST       Host header to send, if --host is an IP (e.g. main.localhost:8000)

Accounts are shared between simulated users, so on the staging service raise the
per-user limit, e.g. THROTTLE_USER=100000/hour, or the results will be throttling.
Admins are left out: in production they need two-factor codes.
'''

import os
import random
import threading
import time

from locust import HttpUser, between, task

PASSWORD = os.environ.get('LOADTEST_PASSWORD', 'Demo-Hms-2026!')
HOST_HEADER = os.environ.get('LOADTEST_HOST')
SEARCHES = ['ad', 'ola', 'musa', 'chi', 'eze', 'bello', 'MRN', '080']

# One sign-in per account, shared by every simulated user of that role, refreshed before
# the 15-minute access token expires (sign-ins are rate limited per address)
_tokens = {}
_lock = threading.Lock()


class StaffUser(HttpUser):
    abstract = True
    email = ''
    wait_time = between(5, 20)  # people pause between actions

    def on_start(self):
        if HOST_HEADER:
            self.client.headers['Host'] = HOST_HEADER
        self.authorize()
        self.last_poll = {}

    def authorize(self):
        with _lock:
            cached = _tokens.get(self.email)
            if cached is None or time.time() - cached['at'] > 12 * 60:
                response = self.client.post(
                    '/api/v1/auth/login/', json={'email': self.email, 'password': PASSWORD}, name='sign in'
                )
                response.raise_for_status()
                cached = _tokens[self.email] = {'access': response.json()['access'], 'at': time.time()}
        self.client.headers['Authorization'] = f'Bearer {cached["access"]}'

    def get(self, path, name=None, **params):
        self.authorize()
        return self.client.get(path, params=params or None, name=name or path)

    def poll(self, key, every_seconds, path, **params):
        '''A screen left open: refreshes on its own schedule, whatever the person is doing.'''
        now = time.time()
        if now - self.last_poll.get(key, 0) >= every_seconds:
            self.last_poll[key] = now
            self.get(path, **params)

    @task(10)
    def open_screens(self):
        self.poll('bell', 30, '/api/v1/notifications/unread-count/')

    def search_patients(self):
        self.get('/api/v1/patients/', name='/api/v1/patients/?search', search=random.choice(SEARCHES))  # noqa: S311

    def open_a_patient(self):
        patients = self.get('/api/v1/patients/', name='/api/v1/patients/ (list)').json().get('results') or []
        if patients:
            patient = random.choice(patients)  # noqa: S311
            self.get(f'/api/v1/patients/{patient["id"]}/', name='/api/v1/patients/[id]/')


class FrontDesk(StaffUser):
    weight = 3
    email = 'receptionist@demo.hms'

    @task(10)
    def queue_board(self):
        self.poll('queue', 15, '/api/v1/queue/')

    @task(3)
    def find_patient(self):
        self.search_patients()

    @task(1)
    def appointments(self):
        self.get('/api/v1/appointments/', name='/api/v1/appointments/')


class Doctor(StaffUser):
    weight = 3

    def on_start(self):
        self.email = random.choice(['doctor@demo.hms', 'doctor.paeds@demo.hms', 'doctor.medicine@demo.hms'])  # noqa: S311
        super().on_start()

    @task(8)
    def my_queue(self):
        self.poll('queue', 15, '/api/v1/queue/')

    @task(3)
    def open_a_visit(self):
        visits = self.get('/api/v1/visits/', name='/api/v1/visits/ (list)').json().get('results') or []
        if visits:
            visit = random.choice(visits)  # noqa: S311
            self.get(f'/api/v1/visits/{visit["id"]}/', name='/api/v1/visits/[id]/')

    @task(1)
    def look_up_patient(self):
        self.open_a_patient()


class Nurse(StaffUser):
    weight = 2
    email = 'nurse@demo.hms'

    @task(10)
    def queue(self):
        self.poll('queue', 15, '/api/v1/queue/')

    @task(2)
    def vitals_history(self):
        self.get('/api/v1/vitals/', name='/api/v1/vitals/')


class Cashier(StaffUser):
    weight = 2
    email = 'cashier@demo.hms'

    @task(5)
    def invoices(self):
        invoices = self.get('/api/v1/billing/invoices/', name='/api/v1/billing/invoices/ (list)').json()
        results = invoices.get('results') or []
        if results:
            invoice = random.choice(results)  # noqa: S311
            self.get(f'/api/v1/billing/invoices/{invoice["id"]}/', name='/api/v1/billing/invoices/[id]/')

    @task(1)
    def daily_summary(self):
        self.get('/api/v1/billing/summary/', name='/api/v1/billing/summary/')


class Lab(StaffUser):
    weight = 1
    email = 'labtech@demo.hms'

    @task(10)
    def work_list(self):
        self.poll('lab', 30, '/api/v1/lab/test-orders/', status='pending')


class Pharmacy(StaffUser):
    weight = 1
    email = 'pharmacist@demo.hms'

    @task(10)
    def prescription_queue(self):
        self.poll('pharmacy', 30, '/api/v1/prescriptions/', pending='true')

    @task(1)
    def stock(self):
        self.get('/api/v1/pharmacy/drugs/', name='/api/v1/pharmacy/drugs/', low_stock='true')
