from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class InvitationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    EXPIRED = "expired", "Expired"
    REVOKED = "revoked", "Revoked"

class Invitation(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    inviter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations"
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_invitations"
    )

    recipient_email = models.EmailField(null=True, blank=True)
    purpose = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=128, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=InvitationStatus.choices, default=InvitationStatus.PENDING, db_index=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_invitations"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.purpose} invitation ({self.id})"

    @property
    def is_pending(self):
        return self.status == InvitationStatus.PENDING

    @property
    def is_accepted(self):
        return self.status == InvitationStatus.ACCEPTED

    @property
    def is_revoked(self):
        return self.status == InvitationStatus.REVOKED

    @property
    def has_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return self.is_pending and not self.has_expired
