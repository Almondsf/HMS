from .serializers import DrugSerializer, DispenseTransactionSerializer
from .models import Drug, DispenseTransaction
from rest_framework import viewsets
from authentication.permissions import Role, allow_roles


class DrugViewSet(viewsets.ModelViewSet):
    serializer_class = DrugSerializer
    queryset = Drug.objects.all()
    permission_classes = [allow_roles(
        read=[Role.DOCTOR, Role.NURSE],
        write=[Role.PHARMACIST, Role.ADMIN],
    )]

class DispenseTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = DispenseTransactionSerializer
    queryset = DispenseTransaction.objects.all()
    permission_classes = [allow_roles(read=[Role.ADMIN], write=[Role.PHARMACIST])]
    # Dispensing already moved stock, so records are create-only (no edit/delete)
    http_method_names = ['get', 'post', 'head', 'options']
