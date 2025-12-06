from django.shortcuts import render
from .serializers import TestsSerializer, TestOrderSerializer, TestResultSerializer
from .models import Tests, TestOrder, TestResult
from rest_framework import viewsets, permissions

# Create your views here.

class TestsViewSet(viewsets.ModelViewSet):
    queryset = Tests.objects.all()
    serializer_class = TestsSerializer
    permission_classes = [permissions.IsAuthenticated]

class TestOrderViewSet(viewsets.ModelViewSet):
    queryset = TestOrder.objects.all()
    serializer_class = TestOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

class TestResultViewSet(viewsets.ModelViewSet):
    queryset = TestResult.objects.all()
    serializer_class = TestResultSerializer
    permission_classes = [permissions.IsAuthenticated]