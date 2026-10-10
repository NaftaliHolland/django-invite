# django-invite

A small, reusable Django application for managing invitations.

`django-invite` handles the invitation lifecycle: creating invitations, generating tokens, tracking their state, validating them, and accepting, revoking, or expiring them.

It does **not** send emails, SMS messages, or create users. Those things belong to the application using the package.

## What it does

An invitation can be used for many things:

* Inviting a user to an organization
* Inviting someone to a project
* Inviting someone to create an account

The package does not need to know what an invitation represents.

Its job is to manage the invitation itself.

### Invitation lifecycle

An invitation starts as `PENDING` and can move to one of three final states:

```text
             ┌──────────> ACCEPTED
             │
PENDING ─────┼──────────> REVOKED
             │
             └──────────> EXPIRED
```

Once an invitation is accepted, revoked, or expired, it cannot transition to another state.

An invitation is also considered invalid when its expiration time has passed, even if its stored status is still `PENDING`.

## Installation
Not yet published to PyPI.  Soon :)

<!--Install the package:

```bash
pip install django-invite
```

Add it to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_invitations",
]
```

Run migrations:

```bash
python manage.py migrate
``` -->

## Creating an invitation

Use the service functions rather than changing invitation state directly.

```python
from django_invitations.services import create_invitation

invitation = create_invitation(
    inviter=request.user,
    recipient_email="teacher@example.com",
    purpose="school_teacher",
    expires_at=expires_at,
)
```

The invitation is created as `PENDING` and receives a unique, unpredictable token.

> [!IMPORTANT]
> The returned invitation will have an additional `raw_token` which will not be persisted to the db.
> This is the token that should be used to accept invitations.
> The `INVITE_CREATED_CALLBACK` and the `invitation_created` signal receiver will be able to access `invitation.raw_token`.

> [!NOTE]
> THIS TOKEN CANNOT BE ACCESSED AGAIN.

## Sending the invitation

Notification delivery belongs to your application.

For example, you can configure a callback:

```python
INVITATIONS = {
    "INVITE_CREATED_CALLBACK": "notifications.services.send_invitation",
}
```

Then implement the notification in your own application:

```python
def send_invitation(invitation):
    # Send email, SMS, etc.
    ...
```

The package emits its lifecycle event after the database transaction commits. Your application can therefore use the event to perform its own work without the package needing to know how notifications are delivered.

Django signals and configured callbacks are independent. You can use either or both.

## Accepting an invitation

```python
from django_invitations.services import accept_invitation

invitation = accept_invitation(
    token=token,
    user=request.user,
)
```
> [!IMPORTANT]
> `token` has to be the `raw_token` returned by `create_invitation`.
> The `token_hash` should not be used as an invite accept token.


The service checks that the invitation is still valid before accepting it.

It records:

* The user who accepted it
* When it was accepted
* The new invitation state

Concurrent requests are handled using database locking so that the same invitation cannot be successfully accepted twice.

## Revoking an invitation

```python
from django_invitations.services import revoke_invitation

invitation = revoke_invitation(invitation)
```

Only a pending invitation can be revoked.

## Expiring an invitation

An invitation becomes invalid automatically when its expiration time passes. A background task is not required for this.

An invitation can also be explicitly transitioned to `EXPIRED`:

```python
from django_invitations.services import expire_invitation

invitation = expire_invitation(invitation)
```

This distinction is intentional. An invitation can be **expired by time** without its database status having been explicitly changed to `EXPIRED`.

## Looking up an invitation

Invitations can be retrieved using their token:

```python
from django_invitations.services import get_invitation_by_token

invitation = get_invitation_by_token(token, is_raw=True)
```
If `is_raw` it uses the raw_token to get the invitation (This should be used when accepting an invitation).
`is_raw` is `True` by default.

## Rotating an invitation's token

Tokens are stored hashed, so the original link cannot be recovered after creation. To send an invitation again, or to cut off a link you think has leaked, rotate its token:

```
from django_invitations.services import rotate_token

invitation = rotate_token(invitation=invitation)

send_invitation_email(invitation.recipient_email, invitation.raw_token)
```

Rotation:

- Generates a new token and stores only its hash.
- Makes the old token stop working immediately.
- Returns the invitation with the new `raw_token`, available on that returned instance only. Your application is responsible for delivering the new link.
- Does not change the invitation's status or emit an event.

Only pending invitations can be rotated. Accepted, revoked, and explicitly expired invitations raise the matching exception.

### Rotating an invitation that expired by time

An invitation that has passed its expiration time cannot be rotated unless you pass a new expiration:

```
from datetime import timedelta
from django.utils import timezone

invitation = rotate_token(
    invitation=invitation,
    expires_at=timezone.now() + timedelta(days=3),
)
```

The new `expires_at` must be in the future and cannot exceed `MAX_TTL`. An invitation whose status is `EXPIRED` can never be revived this way.

## Events

The package provides lifecycle events for:

* `invitation_created`
* `invitation_accepted`
* `invitation_revoked`
* `invitation_expired`

For example:

```python
from django.dispatch import receiver
from django_invitations.events import invitation_created


@receiver(invitation_created)
def handle_invitation_created(sender, invitation, **kwargs):
    ...
```

Events are emitted **after the surrounding database transaction commits**.

This means an invitation that is rolled back does not produce an invitation event.

## Errors

The service layer raises invitation-specific exceptions when an operation cannot be performed.

For example:

```python
from django_invitations.exceptions import InvitationExpiredError

try:
    accept_invitation(invitation, user)
except InvitationExpiredError:
    ...
```

The package provides exceptions for common lifecycle failures, including:

* `InvitationError`
* `InvitationExpiredError`
* `InvitationRevokedError`
* `InvitationAlreadyAcceptedError`
* `InvalidInvitationError`

## Configuration

All callbacks are optional.
`MAX_TTL` defines the maximum lifetime of an invitation.
`MAX_TTL` will also be used to calculate the default `expires_at` if it is not set explicitly when calling `create_invitation()`.

`REQUIRE_RECIPIENT_MATCH` if set to `True`, it will match the email against `recipient.email` or `recipient_email` before accepting and invitation.
This is the default behavior

You can configure only the callbacks you need:

```python
INVITATIONS = {
    "INVITE_CREATED_CALLBACK": "myapp.services.send_invitation",
    "INVITE_ACCEPTED_CALLBACK": "myapp.services.invitation_accepted",
    "INVITE_REVOKED_CALLBACK": "myapp.services.invitation_revoked",
    "INVITE_EXPIRED_CALLBACK": "myapp.services.invitation_expired",

    "RECIPIENT_MATCH": "myapp.services.validate_recipient",

    "MAX_TTL": 7 * 24 * 60 * 60,
    "REQUIRE_RECIPIENT_MATCH": True,
}
```

Or configure nothing:

```python
INVITATIONS = {}
```
Defaults for `MAX_TTL` and `REQUIRE_EMAIL_MATCH` will be used.

When no callback is configured, the lifecycle still works normally.

Callbacks receive the invitation instance:

```python
def send_invitation(invitation):
    print(invitation.recipient_email)
```

The package resolves configured functions using Django's normal import utilities.


## What django-invite does not do

`django-invite` deliberately does not try to be an invitation system for your entire application.

It does **not**:

* Send email
* Send SMS
* Send WhatsApp messages
* Send push notifications
* Create users
* Set passwords
* Assign roles
* Create memberships
* Implement application-specific business logic
* Provide a task queue or background worker
* Provide retries for failed notifications

For example, if an invitation is for a teacher joining a school, the package does not know what a "teacher" or "school" is. Your application decides what accepting that invitation means.

This keeps the package small and reusable.

## How it works

1. Your application calls `create_invitation()`.
2. `django-invite` creates the invitation, generates its token, and manages its lifecycle.
3. Once the transaction commits, `django-invite` emits the appropriate lifecycle event.
4. Your application can listen for the event using a Django signal or an optional callback.
5. Your application decides what to do next, such as sending an email, sending an SMS, or creating related records.

The flow is:

`Application → django-invite → lifecycle event → Application-specific action`

`django-invite` manages the invitation. Your application decides what the invitation means and what should happen when its state changes.

The goal is a small public API with predictable lifecycle behavior that can be understood quickly by another Django developer.
