'''
Vital-sign rules: plausibility limits (to catch typos) and abnormal / critical
flags. Thresholds follow common adult early-warning practice; review them
with your clinical lead before relying on them for alerts.
'''

from decimal import Decimal

# Values outside these are almost certainly data-entry errors
PLAUSIBLE_RANGES = {
    'temperature_c': (25, 45),
    'pulse_bpm': (20, 250),
    'respiratory_rate': (4, 80),
    'systolic_bp': (50, 300),
    'diastolic_bp': (20, 200),
    'spo2_percent': (50, 100),
    'weight_kg': (Decimal('0.3'), 400),
    'height_cm': (20, 250),
    'blood_glucose_mmol': (Decimal('0.5'), 50),
    'pain_score': (0, 10),
}

MEASUREMENTS = tuple(PLAUSIBLE_RANGES)

# (field, test, flag, critical?)
_RULES = [
    ('temperature_c', lambda v: v >= 40, 'very high temperature', True),
    ('temperature_c', lambda v: 38 <= v < 40, 'fever', False),
    ('temperature_c', lambda v: v < 35, 'low temperature', True),
    ('pulse_bpm', lambda v: v > 130, 'very fast pulse', True),
    ('pulse_bpm', lambda v: 100 < v <= 130, 'fast pulse', False),
    ('pulse_bpm', lambda v: v < 40, 'very slow pulse', True),
    ('pulse_bpm', lambda v: 40 <= v < 50, 'slow pulse', False),
    ('respiratory_rate', lambda v: v > 24 or v < 10, 'abnormal breathing rate', True),
    ('respiratory_rate', lambda v: 20 < v <= 24, 'fast breathing', False),
    ('spo2_percent', lambda v: v < 90, 'very low oxygen saturation', True),
    ('spo2_percent', lambda v: 90 <= v < 94, 'low oxygen saturation', False),
    ('systolic_bp', lambda v: v >= 180, 'very high blood pressure', True),
    ('systolic_bp', lambda v: 140 <= v < 180, 'high blood pressure', False),
    ('systolic_bp', lambda v: v < 90, 'low blood pressure', True),
    ('diastolic_bp', lambda v: v >= 120, 'very high blood pressure', True),
    ('diastolic_bp', lambda v: 90 <= v < 120, 'high blood pressure', False),
    ('blood_glucose_mmol', lambda v: v < 4, 'low blood sugar', True),
    ('blood_glucose_mmol', lambda v: v > 11, 'high blood sugar', False),
    ('pain_score', lambda v: v >= 7, 'severe pain', False),
]


def implausible(values):
    '''{field: message} for values outside physiological limits.'''
    errors = {}
    for field, (low, high) in PLAUSIBLE_RANGES.items():
        value = values.get(field)
        if value is not None and not low <= value <= high:
            errors[field] = f'{value} looks wrong; expected between {low} and {high}.'
    systolic, diastolic = values.get('systolic_bp'), values.get('diastolic_bp')
    if systolic is not None and diastolic is not None and diastolic >= systolic:
        errors['diastolic_bp'] = 'Diastolic pressure must be lower than systolic.'
    return errors


def assess(values):
    '''(flags, is_critical) for a set of readings; each flag is reported once.'''
    flags, critical = [], False
    for field, test, flag, is_critical in _RULES:
        value = values.get(field)
        if value is not None and test(value):
            if flag not in flags:
                flags.append(flag)
            critical = critical or is_critical
    return flags, critical
