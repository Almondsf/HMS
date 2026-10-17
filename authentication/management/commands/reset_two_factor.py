from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_public_schema_name, schema_context

from authentication import two_factor
from authentication.models import User


class Command(BaseCommand):
    help = (
        "Remove someone's two-factor sign-in after they lost their phone and recovery codes; they set it up "
        'again at their next sign-in, and are signed out everywhere. Check their identity first.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--schema', default=get_public_schema_name(), help='The hospital; default: the platform')

    def handle(self, *args, email, schema, **options):
        with schema_context(schema):
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                raise CommandError(f'No user {email} in "{schema}".')
            two_factor.reset(user)
        self.stdout.write(self.style.SUCCESS(f'Two-factor sign-in removed for {email} ({schema}).'))
