'''
The notification centre: deliver a notification to the staff who need to act.

    inbox.notify(inbox.staff(Role.PHARMACIST), kind='clinical.prescribed', title='New prescription', link='/pharmacy')

The person whose action caused the event is never notified about it, and a
notification isn't repeated while an identical one (same kind and link) is
still unread, so repeated events (e.g. low stock) don't pile up.
'''

from audit import context
from authentication.models import User

from .models import Notification

Level = Notification.Level


def staff(*roles):
    '''Active staff with any of these roles.'''
    return User.objects.filter(user_type__in=roles, is_active=True)


def notify(recipients, *, kind, title, body='', link='', level=Level.INFO, once=False):
    '''once: never send this kind (and link) to someone twice, even after they read it.'''
    actor = context.current_user()
    ids = {user.pk for user in recipients if user is not None and user.is_active}
    if actor is not None and getattr(actor, 'pk', None):
        ids.discard(actor.pk)
    if link or once:
        earlier = Notification.objects.filter(recipient_id__in=ids, kind=kind, link=link)
        if not once:
            earlier = earlier.filter(read_at__isnull=True)
        ids -= set(earlier.values_list('recipient_id', flat=True))
    return Notification.objects.bulk_create(
        Notification(recipient_id=pk, kind=kind, title=title[:150], body=body[:300], link=link, level=level)
        for pk in sorted(ids)
    )
