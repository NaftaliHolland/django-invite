from django.core.exceptions import ImproperlyConfigured
from django.dispatch import Signal
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

from .conf import get_event_handler


invitation_created = Signal()
invitation_accepted = Signal()
invitation_revoked = Signal()
invitation_expired = Signal()


class InvitationEventSender:
    pass


def emit(signal, handler_name, invitation):
    signal.send(
        sender=InvitationEventSender,
        invitation=invitation,
    )

    handler = get_event_handler(handler_name)

    if handler is not None:
        handler(invitation)

def emit_invitation_created(invitation):

    emit(
        invitation_created,
        "INVITE_CREATED_CALLBACK",
        invitation,
    )

def emit_invitation_accepted(invitation):

    emit(
        invitation_accepted,
        "INVITE_ACCEPTED_CALLBACK",
        invitation,
    )

def emit_invitation_revoked(invitation):

    emit(
        invitation_revoked,
        "INVITE_REVOKED_CALLBACK",
        invitation,
    )

def emit_invitation_expired(invitation):

    emit(
        invitation_expired,
        "INVITE_EXPIRED_CALLBACK",
        invitation,
    )


def emit_after_commit(event, invitation):
    transaction.on_commit(
        lambda: event(invitation)
    )
