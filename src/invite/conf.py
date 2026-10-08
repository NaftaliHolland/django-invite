from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from invite.exceptions import InvitationCallbackNotCallable


SETTING_NAME = "INVITATIONS"

DEFAULTS = {
    "INVITE_CREATED_CALLBACK": None,
    "INVITE_ACCEPTED_CALLBACK": None,
    "INVITE_REVOKED_CALLBACK": None,
    "INVITE_EXPIRED_CALLBACK": None,
}


def get_settings():

    configured = getattr(settings, SETTING_NAME, {})

    if not isinstance(configured, dict):
        raise ImproperlyConfigured(
            f"{SETTING_NAME} must be a dictionary"
        )

    return {
        **DEFAULTS,
        **configured,
    }


def get_event_handler(name):
    path = get_settings().get(name)

    if not path:
        return None
    
    try:
        handler = import_string(path)

    except(ImportError, AttributeError) as exc:
        raise ImproperlyConfigured(
            f"Invalid invitations handler configured for "
        f"{SETTING_NAME}[{name!r}]: {path!r}"
        ) from exc


    if not callable(handler):
        raise InvitationCallbackNotCallable(
            f"Configured invitations handler "
        f"{SETTING_NAME}[{name!r}] must be callable: {path!r}"
        )

    return handler
