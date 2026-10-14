'''
Fill a hospital with realistic demo data, going through the real services so
billing, insurance, stock and the audit trail behave exactly as in use. Then
backdate it across the last 30 days so reports have something to show.

    python manage.py seed_demo --schema main

Local/demo use only. Refuses to run twice on the same hospital.
'''

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context

from authentication.models import User
from billing import services as billing
from billing.models import Invoice, InvoiceLine, Payment, ServiceItem
from clinical import services as clinical
from clinical.models import Consultation, Diagnosis, Visit, VitalSigns
from insurance import services as insurance
from insurance.models import Claim, Coverage, InsuranceProvider
from lab import services as lab
from lab.models import LabTest, TestOrder, TestResult
from pharmacy import services as pharmacy
from pharmacy.models import DispensedItem, DispenseTransaction, Drug
from profiles.models import (
    CashierProfile,
    Department,
    DoctorProfile,
    LabTechProfile,
    NurseProfile,
    PatientProfile,
    PharmacistProfile,
    ReceptionistProfile,
    RecordSequence,
)
from profiles.services import next_mrn
from scheduling import services as scheduling
from scheduling.models import Appointment
from tenants.models import Hospital
from terminology.models import Icd10Code

PASSWORD = 'Demo-Hms-2026!'  # noqa: S105  demo accounts only, documented in DEMO_CREDENTIALS.md
SEED_MARKER = 'demo_seed'

DEPARTMENTS = ['General Outpatient', 'Paediatrics', 'Internal Medicine', 'Antenatal Clinic']

FEES = [
    ('CARD', 'Hospital card', 'registration', '2000', 'manual'),
    ('CONSULT', 'Consultation', 'consultation', '5000', 'consultation_recorded'),
    ('DRESSING', 'Wound dressing', 'procedure', '3000', 'manual'),
    ('INJECTION', 'Injection administration', 'procedure', '1000', 'manual'),
]

LAB_TESTS = [
    ('Malaria parasite (MP)', '1500', 'Not seen'),
    ('Full blood count', '4000', 'Hb 12–16 g/dL; WBC 4–11 ×10⁹/L'),
    ('Widal test', '2500', 'Titre < 1:80'),
    ('Urinalysis', '2000', 'Nitrite negative'),
    ('Fasting blood sugar', '1500', '3.9–5.6 mmol/L'),
    ('Haemoglobin genotype', '3000', ''),
    ('HIV screening', '2000', 'Non-reactive'),
    ('Lipid profile', '8000', 'Total cholesterol < 5.2 mmol/L'),
]

# name, unit, price (None = not priced yet), stock, reorder level
DRUGS = [
    ('Artemether/Lumefantrine 20/120mg', 'tablet', '150', 480, 100),
    ('Paracetamol 500mg', 'tablet', '20', 2000, 300),
    ('Amoxicillin 500mg', 'capsule', '60', 400, 100),
    ('Ciprofloxacin 500mg', 'tablet', '80', 120, 50),
    ('Metformin 500mg', 'tablet', '40', 600, 120),
    ('Amlodipine 5mg', 'tablet', '50', 300, 60),
    ('ORS sachet', 'sachet', '100', 60, 20),
    ('Ceftriaxone 1g', 'vial', None, 40, 10),
    ('Folic acid 5mg', 'tablet', '10', 1000, 200),
    ('Ibuprofen 400mg', 'tablet', '30', 500, 100),
]

INSURERS = [
    ('National Health Insurance Authority', 'NHIA', 'nhia', '90', False),
    ('Hygeia HMO', 'HYGEIA', 'hmo', '80', True),
    ('AXA Mansard Health', 'AXA', 'hmo', '100', False),
]

FIRST_NAMES = {
    'female': [
        'Adaeze',
        'Bisi',
        'Chioma',
        'Funke',
        'Halima',
        'Ifeoma',
        'Kemi',
        'Ngozi',
        'Ronke',
        'Zainab',
        'Aisha',
        'Tolu',
    ],
    'male': [
        'Abdullahi',
        'Babatunde',
        'Chinedu',
        'Dayo',
        'Emeka',
        'Ibrahim',
        'Kunle',
        'Musa',
        'Obinna',
        'Segun',
        'Tayo',
        'Yakubu',
    ],
}
LAST_NAMES = [
    'Adeyemi',
    'Okonkwo',
    'Bello',
    'Eze',
    'Lawal',
    'Nwosu',
    'Ogunleye',
    'Abubakar',
    'Okafor',
    'Balogun',
    'Danjuma',
    'Afolabi',
    'Udoh',
    'Olatunji',
]

# Presentations: reason, notes, vitals, diagnoses (code, certainty), lab tests and results, prescriptions
SCENARIOS = {
    'malaria': {
        'reason': 'Fever and headache for 3 days',
        'notes': (
            'Fever, chills, headache, body pains for 3 days.',
            'Febrile, mildly pale.',
            'Uncomplicated malaria',
            'ACT for 3 days, paracetamol, plenty of fluids.',
        ),
        'vitals': {
            'temperature_c': Decimal('38.7'),
            'pulse_bpm': 104,
            'systolic_bp': 118,
            'diastolic_bp': 76,
            'respiratory_rate': 20,
        },
        'diagnoses': [('B54', 'confirmed')],
        'labs': [('Malaria parasite (MP)', 'Seen (++)')],
        'rx': [
            ('Artemether/Lumefantrine 20/120mg', '4 tablets', 'BD', '3 days', 24),
            ('Paracetamol 500mg', '1g', 'TDS', '3 days', 18),
        ],
    },
    'typhoid': {
        'reason': 'Fever and abdominal pain for a week',
        'notes': (
            'Step-ladder fever, abdominal discomfort, poor appetite.',
            'Febrile, mild abdominal tenderness.',
            'Enteric fever',
            'Oral ciprofloxacin for 7 days, hydration.',
        ),
        'vitals': {'temperature_c': Decimal('38.3'), 'pulse_bpm': 96, 'systolic_bp': 112, 'diastolic_bp': 72},
        'diagnoses': [('A01.0', 'provisional')],
        'labs': [('Widal test', 'O 1:160, H 1:160'), ('Full blood count', 'Hb 12.1 g/dL, WBC 4.2')],
        'rx': [('Ciprofloxacin 500mg', '500mg', 'BD', '7 days', 14), ('Paracetamol 500mg', '1g', 'TDS', '3 days', 18)],
    },
    'urti': {
        'reason': 'Cough and sore throat',
        'notes': (
            'Sore throat, cough and runny nose for 4 days.',
            'Inflamed pharynx, chest clear.',
            'Upper respiratory tract infection',
            'Symptomatic care; antibiotics given for purulent tonsils.',
        ),
        'vitals': {'temperature_c': Decimal('37.8'), 'pulse_bpm': 88, 'spo2_percent': 98},
        'diagnoses': [('J06.9', 'confirmed')],
        'labs': [],
        'rx': [('Amoxicillin 500mg', '500mg', 'TDS', '5 days', 15), ('Paracetamol 500mg', '1g', 'TDS', '3 days', 18)],
    },
    'hypertension': {
        'reason': 'Headaches; known hypertensive',
        'notes': (
            'Occipital headaches, missed doses last month.',
            'BP elevated, no focal deficits.',
            'Essential hypertension, poorly controlled',
            'Restart amlodipine, salt reduction, review in 4 weeks.',
        ),
        'vitals': {
            'systolic_bp': 164,
            'diastolic_bp': 98,
            'pulse_bpm': 82,
            'weight_kg': Decimal('88'),
            'height_cm': Decimal('172'),
        },
        'diagnoses': [('I10', 'confirmed')],
        'labs': [('Lipid profile', 'Total cholesterol 5.9 mmol/L')],
        'rx': [('Amlodipine 5mg', '5mg', 'OD', '30 days', 30)],
    },
    'diabetes': {
        'reason': 'Excessive thirst and frequent urination',
        'notes': (
            'Polyuria, polydipsia for 2 months, weight loss.',
            'Overweight, no foot ulcers.',
            'Type 2 diabetes mellitus',
            'Metformin, diet counselling, glucose diary.',
        ),
        'vitals': {
            'blood_glucose_mmol': Decimal('11.8'),
            'systolic_bp': 136,
            'diastolic_bp': 84,
            'weight_kg': Decimal('94'),
            'height_cm': Decimal('168'),
        },
        'diagnoses': [('E11.9', 'confirmed')],
        'labs': [('Fasting blood sugar', '9.1 mmol/L')],
        'rx': [('Metformin 500mg', '500mg', 'BD', '30 days', 60)],
    },
    'uti': {
        'reason': 'Painful urination',
        'notes': (
            'Dysuria and frequency for 3 days.',
            'Suprapubic tenderness, afebrile.',
            'Lower urinary tract infection',
            'Ciprofloxacin for 3 days, fluids.',
        ),
        'vitals': {'temperature_c': Decimal('37.4'), 'pulse_bpm': 84},
        'diagnoses': [('N39.0', 'confirmed')],
        'labs': [('Urinalysis', 'Nitrite +, Leucocytes ++')],
        'rx': [('Ciprofloxacin 500mg', '500mg', 'BD', '3 days', 6)],
    },
    'gastroenteritis': {
        'reason': 'Diarrhoea and vomiting',
        'notes': (
            'Watery stools x6 and vomiting since yesterday.',
            'Mildly dehydrated.',
            'Acute gastroenteritis',
            'Oral rehydration, review if worse.',
        ),
        'vitals': {'temperature_c': Decimal('37.6'), 'pulse_bpm': 102, 'systolic_bp': 104, 'diastolic_bp': 66},
        'diagnoses': [('A09', 'confirmed')],
        'labs': [],
        'rx': [('ORS sachet', '1 sachet', 'after each loose stool', '3 days', 6)],
    },
    'antenatal': {
        'reason': 'Antenatal booking visit',
        'notes': (
            'G2P1 at 16 weeks, no complaints.',
            'Fundal height appropriate.',
            'Normal pregnancy',
            'Routine antenatal care, haematinics.',
        ),
        'vitals': {'systolic_bp': 112, 'diastolic_bp': 70, 'weight_kg': Decimal('68'), 'height_cm': Decimal('163')},
        'diagnoses': [('Z34.9', 'confirmed')],
        'labs': [
            ('Full blood count', 'Hb 11.4 g/dL'),
            ('HIV screening', 'Non-reactive'),
            ('Haemoglobin genotype', 'AA'),
        ],
        'rx': [('Folic acid 5mg', '5mg', 'OD', '30 days', 30)],
    },
    'pneumonia': {
        'reason': 'Cough, fever and difficulty breathing',
        'notes': (
            'Productive cough, fever, breathlessness for 5 days.',
            'Crackles right base, mild respiratory distress.',
            'Community-acquired pneumonia',
            'IV ceftriaxone, review in 48 hours.',
        ),
        'vitals': {'temperature_c': Decimal('39.1'), 'pulse_bpm': 112, 'respiratory_rate': 26, 'spo2_percent': 91},
        'diagnoses': [('J18.9', 'provisional')],
        'labs': [('Full blood count', 'WBC 15.8 (neutrophilia)')],
        'rx': [('Ceftriaxone 1g', '1g IV', 'OD', '3 days', 3)],
    },
    'sickle_crisis': {
        'reason': 'Severe bone pains',
        'notes': (
            'Known SS, generalised bone pains since last night.',
            'In pain, pale, afebrile.',
            'Sickle cell vaso-occlusive crisis',
            'Analgesia, hydration, folic acid.',
        ),
        'vitals': {'pain_score': 8, 'pulse_bpm': 108, 'temperature_c': Decimal('37.2')},
        'diagnoses': [('D57.0', 'confirmed')],
        'labs': [('Full blood count', 'Hb 7.2 g/dL')],
        'rx': [('Ibuprofen 400mg', '400mg', 'TDS', '5 days', 15), ('Folic acid 5mg', '5mg', 'OD', '30 days', 30)],
    },
}

ADULT_SCENARIOS = [
    'malaria',
    'malaria',
    'typhoid',
    'urti',
    'hypertension',
    'diabetes',
    'uti',
    'gastroenteritis',
    'pneumonia',
]


class Command(BaseCommand):
    help = 'Load realistic demo data into a hospital (local/demo use only).'

    def add_arguments(self, parser):
        parser.add_argument('--schema', required=True, help='Hospital to fill, e.g. main')

    def handle(self, *args, schema, **options):
        with schema_context('public'):
            hospital = Hospital.objects.filter(schema_name=schema).first()
            if hospital is None:
                raise CommandError(f'No hospital with schema "{schema}".')
            # Everything visible in the demo
            Hospital.objects.filter(pk=hospital.pk).update(plan=Hospital.Plan.ENTERPRISE)
            hospital.refresh_from_db()

        self.random = random.Random(2026)  # noqa: S311  reproducible demo data, not security
        timezone.activate(ZoneInfo(hospital.timezone))
        with tenant_context(hospital):
            if RecordSequence.objects.filter(name=SEED_MARKER).exists():
                raise CommandError(f'"{hospital.name}" already has demo data.')
            with transaction.atomic():
                self.seed()
                RecordSequence.objects.create(name=SEED_MARKER, last_value=1)
        self.stdout.write(
            self.style.SUCCESS(f'Demo data loaded into {hospital.name}. Credentials: DEMO_CREDENTIALS.md')
        )

    # ---- helpers ----

    def staff(self, role, email, first, last, profile=None, **profile_fields):
        user = User.objects.filter(email=email).first()
        if user is None:
            extra = {'is_staff': True, 'is_admin': True} if role == User.UserType.ADMIN else {}
            user = User.objects.create_user(
                first_name=first, last_name=last, email=email, password=PASSWORD, user_type=role, **extra
            )
        if profile is not None and not profile.objects.filter(user=user).exists():
            profile.objects.create(user=user, **profile_fields)
        return user

    def when(self, days_ago, hour, minute=0):
        day = timezone.localdate() - timedelta(days=days_ago)
        return timezone.make_aware(datetime(day.year, day.month, day.day, hour, minute))

    # ---- the data ----

    def seed(self):
        rnd = self.random
        departments = {name: Department.objects.get_or_create(name=name)[0] for name in DEPARTMENTS}

        self.admin = self.staff('admin', 'admin@demo.hms', 'Ada', 'Admin')
        gp = self.staff('doctor', 'doctor@demo.hms', 'Tunde', 'Bello', DoctorProfile, specialty='General practice')
        paeds = self.staff(
            'doctor', 'doctor.paeds@demo.hms', 'Amina', 'Yusuf', DoctorProfile,
            specialty='Paediatrics', department=departments['Paediatrics'],
        )  # fmt: skip
        medicine = self.staff(
            'doctor', 'doctor.medicine@demo.hms', 'Emeka', 'Obi', DoctorProfile,
            specialty='Internal medicine', department=departments['Internal Medicine'],
        )  # fmt: skip
        DoctorProfile.objects.filter(user=gp).update(department=departments['General Outpatient'])
        self.nurse = self.staff('nurse', 'nurse@demo.hms', 'Ngozi', 'Eze', NurseProfile)
        self.receptionist = self.staff('receptionist', 'receptionist@demo.hms', 'Funmi', 'Ade', ReceptionistProfile)
        self.cashier = self.staff('cashier', 'cashier@demo.hms', 'Kemi', 'Oladipo', CashierProfile)
        self.pharmacist = self.staff('pharmacist', 'pharmacist@demo.hms', 'Yusuf', 'Musa', PharmacistProfile)
        self.labtech = self.staff('lab_tech', 'labtech@demo.hms', 'Chidi', 'Okafor', LabTechProfile)
        self.doctors = {'gp': gp, 'paeds': paeds, 'medicine': medicine}

        for code, name, category, price, charge_on in FEES:
            ServiceItem.objects.get_or_create(
                code=code, defaults={'name': name, 'category': category, 'price': price, 'charge_on': charge_on}
            )
        self.tests = {
            name: LabTest.objects.get_or_create(name=name, defaults={'cost': cost, 'normal_range': normal})[0]
            for name, cost, normal in LAB_TESTS
        }
        self.drugs = {
            name: Drug.objects.get_or_create(
                name=name,
                defaults={'unit': unit, 'unit_price': price, 'quantity_in_stock': stock, 'reorder_level': reorder},
            )[0]
            for name, unit, price, stock, reorder in DRUGS
        }
        providers = [
            InsuranceProvider.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'kind': kind,
                    'default_coverage_percent': percent,
                    'requires_authorization': auth,
                },
            )[0]
            for name, code, kind, percent, auth in INSURERS
        ]
        self.codes = {code.code: code for code in Icd10Code.objects.all()}

        patients = self.make_patients(28)
        # About a third of patients are insured
        self.coverage = {}
        for patient in rnd.sample(patients, 10):
            provider = rnd.choice(providers)
            self.coverage[patient.pk] = Coverage.objects.create(
                patient=patient, provider=provider, member_number=f'{provider.code}-{rnd.randint(100000, 999999)}',
                plan_name=rnd.choice(['Standard', 'Family', 'Gold']), valid_from=date.today() - timedelta(days=365),
            )  # fmt: skip

        # 30 days of history: 1-3 visits a day
        for days_ago in range(30, 0, -1):
            for _ in range(rnd.randint(1, 3)):
                self.past_visit(rnd.choice(patients), days_ago)

        self.today(patients)
        self.stdout.write(
            f'  {len(patients)} patients, {Visit.objects.count()} visits, {Invoice.objects.count()} invoices'
        )

    def make_patients(self, count):
        rnd = self.random
        patients = []
        for index in range(count):
            gender = rnd.choice(['female', 'male'])
            child = index % 6 == 0
            born = date.today() - timedelta(days=rnd.randint(2, 11) * 365 if child else rnd.randint(19, 72) * 365)
            user = User.objects.create_user(
                first_name=rnd.choice(FIRST_NAMES[gender]),
                last_name=rnd.choice(LAST_NAMES),
                email=None if rnd.random() < 0.6 else f'patient{index}@example.ng',
                password=None,
                user_type=User.UserType.PATIENT,
                gender=gender,
                date_of_birth=born,
                phone_number=f'+23480{rnd.randint(10000000, 99999999)}',
                address=rnd.choice(
                    ['Ikeja, Lagos', 'Yaba, Lagos', 'Wuse, Abuja', 'Bodija, Ibadan', 'GRA, Port Harcourt']
                ),
            )
            genotype = 'SS' if index == 3 else rnd.choice(['AA', 'AA', 'AA', 'AS', 'AC'])
            patients.append(
                PatientProfile.objects.create(
                    user=user,
                    mrn=next_mrn(),
                    blood_group=rnd.choice(['O+', 'O+', 'A+', 'B+', 'AB+', 'O-']),
                    genotype=genotype,
                    allergies='Penicillin' if index % 9 == 2 else '',
                )
            )
        return patients

    def doctor_for(self, patient, scenario):
        if patient.user.date_of_birth and (date.today() - patient.user.date_of_birth).days < 16 * 365:
            return self.doctors['paeds']
        if scenario in ('hypertension', 'diabetes', 'sickle_crisis'):
            return self.doctors['medicine']
        return self.doctors['gp']

    def scenario_for(self, patient):
        if patient.genotype == 'SS' and self.random.random() < 0.5:
            return 'sickle_crisis'
        if patient.user.gender == 'female' and self.random.random() < 0.15:
            return 'antenatal'
        return self.random.choice(ADULT_SCENARIOS)

    def consult(self, visit, scenario_name, doctor):
        scenario = SCENARIOS[scenario_name]
        subjective, objective, assessment, plan = scenario['notes']
        return clinical.record_consultation(
            doctor_user=doctor,
            visit=visit,
            subjective=subjective,
            objective=objective,
            assessment=assessment,
            plan=plan,
            diagnoses=[
                {'code': self.codes[code], 'kind': 'primary' if i == 0 else 'secondary', 'certainty': certainty}
                for i, (code, certainty) in enumerate(scenario['diagnoses'])
            ],
            prescriptions=[
                {
                    'drug': self.drugs[drug],
                    'medication_name': drug,
                    'dosage': dose,
                    'frequency': frequency,
                    'duration': duration,
                    'quantity': quantity,
                }
                for drug, dose, frequency, duration, quantity in scenario['rx']
            ],
            lab_tests=[self.tests[name] for name, _ in scenario['labs']],
            lab_reason=assessment if scenario['labs'] else '',
        )

    def past_visit(self, patient, days_ago):
        rnd = self.random
        scenario_name = self.scenario_for(patient)
        scenario = SCENARIOS[scenario_name]
        doctor = self.doctor_for(patient, scenario_name)

        visit = clinical.open_visit(
            patient=patient, assigned_doctor=doctor.doctorprofile, reason_for_visit=scenario['reason']
        )
        clinical.record_vitals(visit=visit, by=self.nurse, **scenario['vitals'])
        if rnd.random() < 0.5:
            level = 'urgent' if scenario_name in ('pneumonia', 'sickle_crisis') else 'standard'
            clinical.triage(visit=visit, by=self.nurse, level=level)
        clinical.start_visit(visit=visit, by=doctor)
        consultation = self.consult(visit, scenario_name, doctor)

        # Lab results come back
        results = dict(scenario['labs'])
        for result in TestResult.objects.filter(order__consultation=consultation).select_related('test'):
            lab.record_result(result=result, labtech_user=self.labtech, status='collected')
            lab.record_result(
                result=result, labtech_user=self.labtech, status='completed', result_value=results[result.test.name]
            )

        self.dispense(consultation)
        clinical.complete_visit(visit=visit, by=doctor)

        self.bill(visit, recent=days_ago <= 3)
        self.backdate(visit, consultation, self.when(days_ago, rnd.randint(8, 15), rnd.choice([0, 15, 30, 45])))

    def dispense(self, consultation):
        '''Give what's in stock; anything short the patient buys elsewhere (as in real life).'''
        items = []
        for prescription in consultation.prescriptions.select_related('drug'):
            if prescription.drug is None:
                continue
            prescription.drug.refresh_from_db()
            if prescription.drug.quantity_in_stock >= prescription.quantity:
                items.append(
                    {
                        'prescription': prescription,
                        'drug': prescription.drug,
                        'quantity_dispensed': prescription.quantity,
                    }
                )
        if items:
            pharmacy.dispense(pharmacist_user=self.pharmacist, items=items)

    def bill(self, visit, recent=False):
        rnd = self.random
        invoice = Invoice.objects.filter(visit=visit, status=Invoice.Status.DRAFT).first()
        if invoice is None:
            return
        if invoice.lines.filter(needs_price=True, voided=False).exists():
            if recent:
                return  # left open: shows the "needs price" flow
            for line in invoice.lines.filter(needs_price=True):
                billing.price_line(line=line, unit_price=Decimal('3500'))
        if recent and rnd.random() < 0.3:
            return  # still being billed
        billing.issue_invoice(invoice=invoice)

        coverage = self.coverage.get(visit.patient_id)
        if coverage is not None:
            claim = insurance.create_claim(
                invoice=invoice, coverage=coverage,
                authorization_code=(
                    f'PA-{rnd.randint(10000, 99999)}' if coverage.provider.requires_authorization else ''
                ),
            )  # fmt: skip
            outcome = rnd.choices(['draft', 'submitted', 'approved', 'paid', 'paid', 'rejected'])[0]
            if outcome != 'draft':
                insurance.submit_claim(claim=claim)
            if outcome in ('approved', 'paid'):
                insurance.record_response(claim=claim, approved_amount=claim.claimed_amount)
            if outcome == 'paid':
                insurance.record_claim_payment(
                    claim=claim,
                    amount=claim.claimed_amount,
                    by=self.cashier,
                    reference=f'REMIT-{rnd.randint(1000, 9999)}',
                )
            if outcome == 'rejected':
                insurance.record_response(claim=claim, rejection_reason='Service not covered under plan')

        invoice.refresh_totals()
        due = invoice.patient_due
        if due <= 0:
            return
        roll = rnd.random()
        amount = due if roll < 0.75 else (due / 2).quantize(Decimal('0.01')) if roll < 0.88 else None
        if amount:
            method = rnd.choice(['cash', 'cash', 'transfer', 'card', 'mobile_money'])
            billing.record_payment(
                invoice=invoice, amount=amount, method=method, by=self.cashier,
                reference='' if method == 'cash' else f'{method[:3].upper()}-{rnd.randint(100000, 999999)}',
            )  # fmt: skip

    def unbilled_today(self, unpriced_patient, open_patient):
        """Two patients seen today, nothing paid yet: one with an unpriced drug (needs price), one open."""
        doctor = self.doctors['gp']
        for patient, scenario_name in ((unpriced_patient, 'pneumonia'), (open_patient, 'malaria')):
            visit = clinical.open_visit(
                patient=patient,
                assigned_doctor=doctor.doctorprofile,
                reason_for_visit=SCENARIOS[scenario_name]['reason'],
            )
            clinical.record_vitals(visit=visit, by=self.nurse, **SCENARIOS[scenario_name]['vitals'])
            clinical.start_visit(visit=visit, by=doctor)
            consultation = self.consult(visit, scenario_name, doctor)
            self.dispense(consultation)
            clinical.complete_visit(visit=visit, by=doctor)

    def backdate(self, visit, consultation, arrived):
        '''Move a finished visit and everything it produced to `arrived`.'''
        rnd = self.random
        started = arrived + timedelta(minutes=rnd.randint(10, 75))
        seen = started + timedelta(minutes=rnd.randint(8, 25))
        Visit.objects.filter(pk=visit.pk).update(
            visit_date=arrived, created_at=arrived, started_at=started, completed_at=seen,
            triaged_at=arrived + timedelta(minutes=5) if visit.triage_level else None,
        )  # fmt: skip
        VitalSigns.objects.filter(visit=visit).update(recorded_at=arrived + timedelta(minutes=6))
        Consultation.objects.filter(pk=consultation.pk).update(created_at=started + timedelta(minutes=4))
        Diagnosis.objects.filter(consultation=consultation).update(created_at=started + timedelta(minutes=6))
        consultation.prescriptions.update(created_at=started + timedelta(minutes=7))
        TestOrder.objects.filter(consultation=consultation).update(ordered_at=started + timedelta(minutes=8))
        TestResult.objects.filter(order__consultation=consultation).update(
            completed_at=started + timedelta(minutes=rnd.randint(60, 180))
        )
        dispensed_at = seen + timedelta(minutes=20)
        transaction_ids = DispensedItem.objects.filter(prescription__consultation=consultation).values('transaction_id')
        DispenseTransaction.objects.filter(pk__in=transaction_ids).update(
            created_at=dispensed_at, dispensed_at=dispensed_at
        )
        DispensedItem.objects.filter(prescription__consultation=consultation).update(created_at=dispensed_at)

        invoices = Invoice.objects.filter(visit=visit)
        InvoiceLine.objects.filter(invoice__in=invoices).update(created_at=arrived + timedelta(minutes=30))
        invoices.update(created_at=arrived)
        invoices.exclude(issued_at=None).update(issued_at=seen + timedelta(minutes=30))
        Payment.objects.filter(invoice__in=invoices).update(created_at=seen + timedelta(minutes=40))
        Claim.objects.filter(invoice__in=invoices).update(created_at=seen + timedelta(minutes=45))
        Claim.objects.filter(invoice__in=invoices).exclude(submitted_at=None).update(
            submitted_at=min(seen + timedelta(days=1), timezone.now())
        )

    def today(self, patients):
        '''A live queue, today's and tomorrow's appointments.'''
        rnd = self.random
        free = list(patients)
        rnd.shuffle(free)

        # Someone already seen and paid this morning (so today's cash summary isn't empty)
        done = free.pop()
        scenario = 'urti'
        doctor = self.doctors['gp']
        visit = clinical.open_visit(
            patient=done, assigned_doctor=doctor.doctorprofile, reason_for_visit=SCENARIOS[scenario]['reason']
        )
        clinical.record_vitals(visit=visit, by=self.nurse, **SCENARIOS[scenario]['vitals'])
        clinical.start_visit(visit=visit, by=doctor)
        consultation = self.consult(visit, scenario, doctor)
        self.dispense(consultation)
        clinical.complete_visit(visit=visit, by=doctor)
        invoice = Invoice.objects.get(visit=visit, status=Invoice.Status.DRAFT)
        billing.issue_invoice(invoice=invoice)
        billing.record_payment(invoice=invoice, amount=invoice.patient_due, method='cash', by=self.cashier)

        self.unbilled_today(free.pop(), free.pop())

        # The queue: one with the doctor, others waiting with triage and vitals
        waiting = [
            (
                'pneumonia',
                'emergency',
                {'temperature_c': Decimal('39.2'), 'spo2_percent': 88, 'respiratory_rate': 28, 'pulse_bpm': 118},
            ),
            ('malaria', 'urgent', SCENARIOS['malaria']['vitals']),
            ('hypertension', 'standard', SCENARIOS['hypertension']['vitals']),
            ('urti', '', {}),
            ('uti', '', {}),
        ]
        in_room = free.pop()
        visit = clinical.open_visit(
            patient=in_room,
            assigned_doctor=self.doctors['gp'].doctorprofile,
            reason_for_visit=SCENARIOS['typhoid']['reason'],
        )
        clinical.record_vitals(visit=visit, by=self.nurse, **SCENARIOS['typhoid']['vitals'])
        clinical.start_visit(visit=visit, by=self.doctors['gp'])
        for scenario_name, level, vitals in waiting:
            patient = free.pop()
            doctor = self.doctor_for(patient, scenario_name)
            visit = clinical.open_visit(
                patient=patient,
                assigned_doctor=doctor.doctorprofile,
                reason_for_visit=SCENARIOS[scenario_name]['reason'],
            )
            if vitals:
                clinical.record_vitals(visit=visit, by=self.nurse, **vitals)
            if level:
                clinical.triage(visit=visit, by=self.nurse, level=level, notes='Seen at triage desk')

        # Appointments: tomorrow's clinic, a no-show and a cancellation
        tomorrow = timezone.localdate() + timedelta(days=1)
        for hour in (9, 10, 11, 14):
            patient = free.pop()
            starts = timezone.make_aware(datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, 0))
            scheduling.book_appointment(
                patient=patient, doctor=self.doctors['medicine'].doctorprofile, starts_at=starts,
                duration_minutes=20, reason='Follow-up review', booked_by=self.receptionist,
            )  # fmt: skip
        later = timezone.now() + timedelta(days=2)
        cancelled = scheduling.book_appointment(
            patient=free.pop(), doctor=self.doctors['paeds'].doctorprofile,
            starts_at=later.replace(minute=0, second=0, microsecond=0),
            reason='Immunisation', booked_by=self.receptionist,
        )  # fmt: skip
        scheduling.cancel_appointment(appointment=cancelled, reason='Family travelling')
        missed_start = self.when(1, 15)
        Appointment.objects.create(
            patient=free.pop(), doctor=self.doctors['gp'].doctorprofile, starts_at=missed_start,
            ends_at=missed_start + timedelta(minutes=15), reason='Blood pressure check',
            status=Appointment.Status.NO_SHOW, booked_by=self.receptionist,
        )  # fmt: skip
