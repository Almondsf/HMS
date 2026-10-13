from django.contrib import admin

from .models import LabTest, TestOrder, TestResult


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ['name', 'cost', 'normal_range', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']


class TestResultInline(admin.TabularInline):
    model = TestResult
    extra = 0


@admin.register(TestOrder)
class TestOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'ordered_by', 'status', 'ordered_at']
    list_filter = ['status']
    list_select_related = ['patient__user', 'ordered_by__user']
    inlines = [TestResultInline]


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'test', 'status', 'result_value', 'labtech', 'completed_at']
    list_filter = ['status', 'test']
