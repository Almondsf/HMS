from django.db import models


class Icd10Code(models.Model):
    '''
    An ICD-10 diagnosis code. Shared by every hospital (lives in the public
    schema); load a full code list with `manage.py load_icd10`.
    '''

    code = models.CharField(max_length=10, primary_key=True)
    title = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True, help_text='Retired codes stay for history but cannot be chosen.')

    class Meta:
        ordering = ['code']
        verbose_name = 'ICD-10 code'

    def __str__(self):
        return f'{self.code} {self.title}'
