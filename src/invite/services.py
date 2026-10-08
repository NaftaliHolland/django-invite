import secrets
from django.utils import timezone
from .exceptions import (
    InvitationAlreadyAcceptedError,
    InvitationDoesNotExistError,
    InvitationError,
    InvitationExpiredError,
    InvitationRevokedError
)
from .models import Invitation, InvitationStatus
from django.db import transaction
from django.db.models import QuerySet
from .events import emit_after_commit, emit_invitation_accepted, emit_invitation_created, emit_invitation_revoked, emit_invitation_expired

def generate_token():
    return secrets.token_urlsafe(32)

@transaction.atomic
def create_invitation(
    *,
    inviter,
    purpose,
    expires_at,
    recipient=None,
    receipient=None,
    recipient_email=None,

):

    invitation = Invitation.objects.create(
        inviter=inviter,
        recipient=recipient,
        recipient_email=recipient_email,
        purpose=purpose,
        token=generate_token(),
        expires_at=expires_at,
    )
    
    emit_after_commit(emit_invitation_created, invitation)

    return invitation

def get_invitation_by_token(*, token):
    try:
        return Invitation.objects.get(token=token)
    except Invitation.DoesNotExist:
        raise InvitationDoesNotExistError
        
@transaction.atomic
def accept_invitation(
    *,
    invitation,
    accepted_by=None,
):

    invitation = (
        Invitation.objects.select_for_update().get(pk=invitation.pk)
    )

    if invitation.status == InvitationStatus.ACCEPTED:
        raise InvitationAlreadyAcceptedError( "This invitation has already been accepted." )

    if invitation.status == InvitationStatus.REVOKED:
        raise InvitationRevokedError( "This invitation has been revoked." )

    if invitation.status == InvitationStatus.EXPIRED:
        raise InvitationExpiredError( "This invitation has expired." )

    if invitation.has_expired:
        invitation.status = InvitationStatus.EXPIRED
        invitation.save( update_fields=["status"], )
        emit_after_commit(
            emit_invitation_expired,
            invitation,
        )

        raise InvitationExpiredError( "This invitation has expired." )

    if invitation.status != InvitationStatus.PENDING:
        raise InvitationError( f"Invitation cannot be accepted from status " f"'{invitation.status}'." )

    invitation.accepted_by = accepted_by
    invitation.accepted_at = timezone.now()
    invitation.status = InvitationStatus.ACCEPTED

    invitation.save(update_fields=["accepted_by", "accepted_at", "status"])

    emit_after_commit(emit_invitation_accepted, invitation)

    return invitation

@transaction.atomic
def revoke_invitation(*, invitation):
    invitation = (
        Invitation.objects.select_for_update().get(pk=invitation.pk)
    )

    if invitation.status != InvitationStatus.PENDING:
        raise InvitationError(
            f"Only pending invitations can be revoked. "
        f"Current status: '{invitation.status}'"
        )

    invitation.status = InvitationStatus.REVOKED
    invitation.revoked_at = timezone.now()

    invitation.save(update_fields=["status", "revoked_at"])

    emit_after_commit(emit_invitation_revoked, invitation)

    return invitation

@transaction.atomic
def expire_invitation(*, invitation):
    invitation = (
        Invitation.objects.select_for_update().get(pk=invitation.pk)
    )

    if invitation.status != InvitationStatus.PENDING:
        raise InvitationError(
            f"Only pending invitations can be expired. "
        f"Current status: '{invitation.status}'"
        )

    if not invitation.has_expired:
        raise InvitationError(
            "This invitation has not reached its expiration time."
        )

    invitation.status = InvitationStatus.EXPIRED
    invitation.expired_at = timezone.now()

    invitation.save(update_fields=["status", "expired_at"])

    emit_after_commit(emit_invitation_expired, invitation)

    return invitation

def get_invitations(
    *,
    inviter=None,
    recipient=None,
    recipient_email=None,
    purpose=None,
    status=None,
    is_pending=None,
    is_expired=None,
) -> QuerySet[Invitation]:
    """
    Return invitations matching the provided filters.

    All filters are optional.
    """

    queryset = Invitation.objects.all()

    if inviter is not None:
        queryset = queryset.filter(inviter=inviter)

    if recipient is not None:
        queryset = queryset.filter(recipient=recipient)

    if recipient_email is not None:
        queryset = queryset.filter(recipient_email__iexact=recipient_email)

    if purpose is not None:
        queryset = queryset.filter(purpose=purpose)

    if status is not None:
        queryset = queryset.filter(status=status)

    if is_pending is not None:
        if is_pending:
            queryset = queryset.filter(status=InvitationStatus.PENDING)

    if is_expired is not None:
        if is_expired:
            queryset = queryset.filter(expires_at__lte=timezone.now())
        else:
            queryset = queryset.filter(expires_at__gt=timezone.now())

    queryset.order_by("-created_at")

    return queryset
