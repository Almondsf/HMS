from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Everything that runs on a schedule (the hourly Render cron job): SMS reminders, '
        'subscription notices and the daily notification emails.'
    )

    def handle(self, *args, **options):
        for command in ('send_appointment_reminders', 'notify_subscription_status', 'send_notification_digests'):
            try:
                call_command(command, stdout=self.stdout)
            except Exception as exc:  # noqa: BLE001 (one failing job must not stop the others)
                self.stderr.write(f'{command} failed: {exc}')
