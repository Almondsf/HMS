from .serializers import TestsSerializer, TestOrderSerializer, TestResultSerializer
from .models import Tests, TestOrder, TestResult
from rest_framework import viewsets
from authentication.permissions import Role, STAFF_ROLES, allow_roles


class TestsViewSet(viewsets.ModelViewSet):
    queryset = Tests.objects.all()
    serializer_class = TestsSerializer
    permission_classes = [allow_roles(read=STAFF_ROLES, write=[Role.ADMIN, Role.LAB_TECHNICIAN])]

class TestOrderViewSet(viewsets.ModelViewSet):
    queryset = TestOrder.objects.all()
    serializer_class = TestOrderSerializer
    permission_classes = [allow_roles(write=[Role.DOCTOR, Role.LAB_TECHNICIAN, Role.ADMIN])]

class TestResultViewSet(viewsets.ModelViewSet):
    queryset = TestResult.objects.all()
    serializer_class = TestResultSerializer
    permission_classes = [allow_roles(read=[Role.DOCTOR, Role.ADMIN], write=[Role.LAB_TECHNICIAN])]
