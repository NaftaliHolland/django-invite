class InvitationError(Exception):
    """
    Base exeption for all invitation-related errors
    """
    pass

class InvitationRevokedError(InvitationError):
    pass

class InvitationExpiredError(InvitationError):
    pass

class InvitationAlreadyAcceptedError(InvitationError):
    pass

class InvalidInvitationError(InvitationError):
    pass

class InvitationDoesNotExistError(InvitationError):
    pass

class InvitationCallbackNotCallable(InvitationError):
    pass

class MaximumTTLExceededError(InvitationError):
    pass
