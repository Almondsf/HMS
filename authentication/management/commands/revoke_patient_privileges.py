from django.core.management.base import BaseCommand
from django.db.models import Q
from django_tenants.utils import get_public_schema_name, get_tenant_model, schema_context

from audit.recorder import Category, record
from authentication.models import User
from authentication.services import revoke_all_sessions

PRIVILEGED = Q(is_superuser=True) | Q(is_staff=True) | Q(is_admin=True)


class Command(BaseCommand):
    help = (
        'Remove superuser/staff/admin rights from patient accounts in every schema (platform and all '
        'hospitals) and sign them out. Before the registration fix, anyone could create such accounts.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only list the affected accounts')

    def handle(self, *args, dry_run, **options):
        schemas = [get_public_schema_name(), *get_tenant_model().objects.exclude(
            schema_name=get_public_schema_name()
        ).values_list('schema_name', flat=True)]  # fmt: skip

        total = 0
        for schema in schemas:
            with schema_context(schema):
                for user in User.objects.filter(PRIVILEGED, user_type=User.UserType.PATIENT):
                    total += 1
                    flags = [name for name in ('is_superuser', 'is_staff', 'is_admin') if getattr(user, name)]
                    self.stdout.write(f'  [{schema}] {user.email or user.pk}: {", ".join(flags)}')
                    if dry_run:
                        continue
                    user.is_superuser = user.is_staff = user.is_admin = False
                    user.save(update_fields=['is_superuser', 'is_staff', 'is_admin'])
                    user.groups.clear()
                    user.user_permissions.clear()
                    revoke_all_sessions(user)
                    record('privileges_revoked', Category.SECURITY, actor=user, metadata={'removed': flags})

        verb = 'would be fixed' if dry_run else 'fixed'
        self.stdout.write(self.style.SUCCESS(f'{total} patient account(s) {verb}.'))
