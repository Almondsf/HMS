'''Confirmations go out after an appointment is booked or moved (after the booking has committed).'''

from audit import events

from . import services
from .models import SmsMessage


@events.subscribe('scheduling.appointment_booked')
@events.subscribe('scheduling.appointment_rescheduled')
def confirm_appointment(event):
    message = services.queue(event.resource, SmsMessage.Kind.BOOKING)
    if message and message.status == SmsMessage.Status.QUEUED:
        services.send_soon(message)
