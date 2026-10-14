import secrets

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from tenants.models import Hospital
from tenants.services import provision_hospital


class Command(BaseCommand):
    help = 'Create a hospital with its own database schema, address and first admin user.'

    def add_arguments(self, parser):
        parser.add_argument('--name', required=True, help='Display name, e.g. "St Luke\'s Hospital"')
        parser.add_argument('--schema', required=True, help='Identifier, e.g. stlukes (lowercase, digits, _)')
        parser.add_argument('--domain', help='Hostname; defaults to <schema>.<TENANT_BASE_DOMAIN>')
        parser.add_argument('--plan', choices=Hospital.Plan.values, default=Hospital.Plan.BASIC)
        parser.add_argument('--admin-email', required=True)
        parser.add_argument('--admin-first-name', default='Hospital')
        parser.add_argument('--admin-last-name', default='Admin')
        parser.add_argument('--admin-password', help='Omit to generate a strong one (printed once)')

    def handle(self, *args, **options):
        password = options['admin_password'] or secrets.token_urlsafe(16)
        self.stdout.write(f"Creating {options['name']} (this runs all migrations in a new schema)...")
        try:
            hospital, admin = provision_hospital(
                name=options['name'],
                schema_name=options['schema'],
                domain=options['domain'],
                plan=options['plan'],
                admin_email=options['admin_email'],
                admin_password=password,
                admin_first_name=options['admin_first_name'],
                admin_last_name=options['admin_last_name'],
            )
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc

        self.stdout.write(self.style.SUCCESS(f'Created {hospital} at {hospital.get_primary_domain().domain}'))
        self.stdout.write(f'Admin: {admin.email}')
        if not options['admin_password']:
            self.stdout.write(f'Temporary password (shown once, change it after first login): {password}')
