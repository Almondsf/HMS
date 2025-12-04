from django.shortcuts import render
from .serializers import DrugSerializer, DispenseTransactionSerializer, DispensedItemSerializer
from .models import Drug, DispenseTransaction, DispensedItem
from rest_framework import viewsets

# Create your views here.

class DrugViewSet(viewsets.ModelViewSet):
    serializer_class = DrugSerializer
    queryset = Drug.objects.all()
    
class DispenseTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = DispenseTransactionSerializer
    queryset = DispenseTransaction.objects.all()
    