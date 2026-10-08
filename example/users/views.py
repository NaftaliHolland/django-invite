from django.shortcuts import render, redirect
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.dispatch import receiver

from invite.models import Invitation
from invite.exceptions import InvitationDoesNotExistError, InvitationError, InvitationExpiredError, InvitationAlreadyAcceptedError, InvalidInvitationError, InvitationRevokedError
from invite.services import create_invitation, accept_invitation, revoke_invitation, get_invitation_by_token, expire_invitation, get_invitations
from invite.events import invitation_created


@login_required
def invite_user(request):
    if request.method == "POST":
        recipient_email = request.POST.get("recipient_email")

        expires_at = timezone.now() + timedelta(days=7)

        invitation = create_invitation(
            inviter=request.user,
            recipient_email=recipient_email,
            purpose="This",
            expires_at=expires_at,
        )

        return render(
            request,
            "users/invitation_created.html",
            {"invitation": invitation},
        )

    return render(request, "users/invite_user.html")

def accept_invitation_view(request, token):
    if not request.user.is_authenticated:
        return redirect(
            f"/accounts/login/?next={request.path}"
        )

    try:
        invitation = get_invitation_by_token(token=token)

    except InvitationDoesNotExistError:
        return render(
            request,
            "users/invitation_error.html",
            {
                "message": "This invitation does not exist or is no longer available."
            },
            status=404,
        )

    if request.method == "GET":
        return render(
            request,
            "users/accept_invitation.html",
            {"invitation": invitation},
        )

    try:
        invitation = accept_invitation(
            invitation=invitation,
            accepted_by=request.user,
        )

    except InvitationAlreadyAcceptedError as exc:
        return render(
            request,
            "users/invitation_error.html",
            {"message": str(exc)},
            status=400,
        )

    except InvitationRevokedError as exc:
        return render(
            request,
            "users/invitation_error.html",
            {"message": str(exc)},
            status=400,
        )

    except InvitationExpiredError as exc:
        return render(
            request,
            "users/invitation_error.html",
            {"message": str(exc)},
            status=400,
        )

    return render(
        request,
        "users/invitation_accepted.html",
        {"invitation": invitation},
    )


@login_required
def revoke_invitation_view(request, token):
    """
    Revoke a pending invitation.
    """
    invitation = get_invitation_by_token(token=token)

    if request.method == "GET":
        return render(
            request,
            "users/revoke_invitation.html",
            {"invitation": invitation},
        )

    try:
        invitation = revoke_invitation(
            invitation=invitation,
        )

    except InvitationError as exc:
        return render(
            request,
            "users/invitation_error.html",
            {
                "message": str(exc),
                "invitation": invitation,
            },
            status=400,
        )

    return render(
        request,
        "users/invitation_revoked.html",
        {"invitation": invitation},
    )


@login_required
def expire_invitation_view(request, token):
    """
    Manually expire an invitation.
    """
    invitation = get_invitation_by_token(token=token)

    if request.method == "GET":
        return render(
            request,
            "users/expire_invitation.html",
            {"invitation": invitation},
        )

    try:
        invitation = expire_invitation(
            invitation=invitation,
        )

    except InvitationError as exc:
        return render(
            request,
            "users/invitation_error.html",
            {
                "message": str(exc),
                "invitation": invitation,
            },
            status=400,
        )

    return render(
        request,
        "users/invitation_expired.html",
        {"invitation": invitation},
    )

@login_required
def invitation_list_view(request):
    invitations = get_invitations()

    return render(
        request,
        "users/invitation_list.html",
        {"invitations": invitations},
    )
