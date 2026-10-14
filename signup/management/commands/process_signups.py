from django.core.management.base import BaseCommand

from signup import services
from signup.models import Signup


class Command(BaseCommand):
    help = (
        'Finish hospital setups interrupted part-way (e.g. by a deploy) and delete signups never verified. '
        'Safe to run at any time; runs on every deploy.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--retry-failed', action='store_true', help='Also retry setups that failed')

    def handle(self, *args, retry_failed, **options):
        retry = list(services.stalled())
        if retry_failed:
            retry += list(Signup.objects.filter(status=Signup.Status.FAILED))
        for signup in retry:
            self.stdout.write(f'Setting up {signup.address} ({signup.email})...')
            signup.status = Signup.Status.PROVISIONING
            signup.save(update_fields=['status', 'updated_at'])
            result = services.provision(signup.pk)
            self.stdout.write(f'  {result.get_status_display()} {result.error}')
        deleted = services.purge_unverified()
        self.stdout.write(self.style.SUCCESS(f'Done: {len(retry)} retried, {deleted} unverified signups deleted.'))
