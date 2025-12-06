from django.contrib import admin
from lab.models import Tests, TestOrder, TestResult

# Register your models here.

admin.site.register(Tests)
admin.site.register(TestOrder)
admin.site.register(TestResult)