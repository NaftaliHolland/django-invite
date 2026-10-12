from django.contrib import admin, messages
from .exceptions import InvitationError
from .models import Invitation
from .services import expire_invitation, revoke_invitation, rotate_token
from .models import Invitation

@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    actions = ["revoke_selected", "expire_selected", "rotate_selected_tokens"]

    list_display = (
        "id",
        "recipient_email",
        "purpose",
        "inviter",
        "recipient",
        "status",
        "created_at",
        "expires_at",
    )

    list_filter = (
        "status",
        "purpose",
        "created_at",
        "expires_at",
    )

    search_fields = (
        "id",
        "recipient_email",
        "inviter__username",
        "inviter__email",
        "recipient__username",
        "recipient__email",
    )

    readonly_fields = (
        "id",
        "token_hash",
        "created_at",
        "accepted_at",
        "revoked_at",
        "expired_at",
    )

    date_hierarchy = "created_at"
    list_select_related = ("inviter", "recipient", "accepted_by")
    list_per_page = 25

    fieldsets = (
        ("Invitation", {
            "fields": (
                "id",
                "purpose",
                "status",
                "recipient_email",
                "inviter",
                "recipient",
            ),
        }),
        ("Lifecycle", {
            "fields": (
                "created_at",
                "expires_at",
                "accepted_at",
                "accepted_by",
                "revoked_at",
                "expired_at",
            ),
        }),
        ("Metadata", {
            "fields": ("meta",),
        }),
        ("Security", {
            "fields": ("token_hash",),
            "classes": ("collapse",),
        }),
    )

    @admin.action(description="Revoke selected invitations", permissions=["change"])
    def revoke_selected(self, request, queryset):
        self.run_bulk(request, queryset, revoke_invitation, "revoked")


    @admin.action(description="Mark selected overdue invitations as expired", permissions=["change"])
    def expire_selected(self, request, queryset):
        self.run_bulk(request, queryset, expire_invitation, "marked as expired")


    @admin.action(description="Rotate token (shows new token once)", permissions=["change"])
    def rotate_selected_tokens(self, request, queryset):
        if queryset.count() > 10:
            self.message_user(
                request,
                "Select at most 10 invitations when rotating tokens.",
                messages.ERROR,
            )
            return

        for invitation in queryset:
            try:
                updated = rotate_token(invitation=invitation)
            except InvitationError as exc:
                self.message_user(
                    request, f"#{invitation.pk}: {exc}", messages.WARNING
                )
                continue

            self.message_user(
                request,
                f"#{updated.pk} new token (shown once, copy it now): {updated.raw_token}",
                messages.SUCCESS,
            )


    def run_bulk(self, request, queryset, service_fn, verb):
        succeeded = 0
        failures = []

        for invitation in queryset:
            try:
                service_fn(invitation=invitation)
                succeeded += 1
            except InvitationError as exc:
                failures.append(f"#{invitation.pk}: {exc}")

        if succeeded:
            self.message_user(
                request,
                f"{succeeded} invitation(s) {verb}.",
                messages.SUCCESS,
            )

        if failures:
            shown = "; ".join(failures[:5])
            extra = f" (+{len(failures) - 5} more)" if len(failures) > 5 else ""
            self.message_user(
                request,
                f"{len(failures)} skipped: {shown}{extra}",
                messages.WARNING,
            )
