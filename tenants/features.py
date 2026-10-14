'''
Which modules a hospital can use, by subscription plan.

    permission_classes = [requires_feature(Feature.LAB), ...]
'''

from django.db import connection, models
from rest_framework.permissions import BasePermission

from .models import Hospital


class Feature(models.TextChoices):
    CLINICAL = 'clinical', 'Front desk & consultations'
    PHARMACY = 'pharmacy', 'Pharmacy'
    LAB = 'lab', 'Laboratory'


PLAN_FEATURES = {
    Hospital.Plan.BASIC: {Feature.CLINICAL, Feature.PHARMACY},
    Hospital.Plan.PRO: {Feature.CLINICAL, Feature.PHARMACY, Feature.LAB},
    Hospital.Plan.ENTERPRISE: set(Feature),
}


def features_for(hospital):
    return PLAN_FEATURES.get(hospital.plan, set())


def has_feature(feature):
    '''Whether the hospital handling the current request has this module.'''
    hospital = getattr(connection, 'tenant', None)
    return isinstance(hospital, Hospital) and feature in features_for(hospital)


def requires_feature(feature):
    class FeatureEnabled(BasePermission):
        message = f"Your hospital's plan doesn't include the {Feature(feature).label} module."

        def has_permission(self, request, view):
            return has_feature(feature)

    return FeatureEnabled
