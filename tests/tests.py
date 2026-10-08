from datetime import timedelta

from django.test import TestCase, SimpleTestCase
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
from invite.conf import SETTING_NAME, get_settings, get_event_handler
from invite.models import Invitation, InvitationStatus
from django.contrib.auth import get_user_model
from django.utils import timezone
from invite.exceptions import InvitationAlreadyAcceptedError, InvitationCallbackNotCallable, InvitationDoesNotExistError, InvitationExpiredError, InvitationRevokedError
from invite.services import create_invitation, accept_invitation, get_invitation_by_token, revoke_invitation, expire_invitation

User = get_user_model()

def invitation_create():
    return

NOT_COLLABLE = "invitation_create"

class SettingsConfTestCase(SimpleTestCase):
    def test_returns_settings_dict(self):
        settings = {
            "INVITE_CREATED_CALLBACK": "invite.tests.invitation_create",
            "INVITE_ACCEPTED_CALLBACK": None,
            "INVITE_REVOKED_CALLBACK": None,
            "INVITE_EXPIRED_CALLBACK": None,
        }

        with patch(f"django.conf.settings.{SETTING_NAME}", settings):
            self.assertEqual(get_settings(), settings)

    @patch(f"django.conf.settings.{SETTING_NAME}", None)
    def test_raises_if_setting_is_none(self):
        with self.assertRaises(ImproperlyConfigured):
            get_settings()

    @patch(
        "invite.conf.get_settings",
        return_value={"INVITE_CREATED_CALLBACK": "invite.tests.does_not_exist"},
    )
    def test_raises_if_handler_attribute_does_not_exist(self, mock_get_settings):
        with self.assertRaises(ImproperlyConfigured):
            get_event_handler("INVITE_CREATED_CALLBACK")

    @patch("invite.conf.get_settings", return_value={"INVITE_CREATED_CALLBACK": "does.not.exist"})
    def test_raises_if_handler_path_is_none(self, mock_get_settings):
        with self.assertRaises(ImproperlyConfigured):
            get_event_handler("INVITE_CREATED_CALLBACK")

    @patch("invite.conf.get_settings", return_value={"INVITE_CREATED_CALLBACK": "invite.tests.invitation_create"})
    def test_gets_the_right_handler(self, mock_settings_get):

        self.assertEqual(invitation_create, get_event_handler("INVITE_CREATED_CALLBACK"))

    @patch("invite.conf.get_settings", return_value={"INVITE_CREATED_CALLBACK": "invite.tests.NOT_COLLABLE"})
    def test_raises_if_not_callable(self, mock_settings_get):
        with self.assertRaises(InvitationCallbackNotCallable):
            get_event_handler("INVITE_CREATED_CALLBACK")

    @patch(f"django.conf.settings.{SETTING_NAME}", "INVITE_NOT_REALLY")
    def test_raises_if_not_dict(self):

        with self.assertRaises(ImproperlyConfigured):
            get_settings()

    @patch("invite.conf.get_settings", return_value={"INVITE_CREATED_CALLBACK": "existing_path_not_really"})
    def test_raises_if_path_not_found(self, mock_get_settings_get):
        with self.assertRaises(ImproperlyConfigured):
            get_event_handler("INVITE_CREATED_CALLBACK")

    def test_returns_none_if_config_does_not_exist(self):
        self.assertIsNone(get_event_handler("DOESNT"))


class InvitationServiceTests(TestCase):
    def setUp(self):
        self.inviter = User.objects.create_user(
            username="testuser",
            password="password"
        )

        self.recipient = User.objects.create_user(
            username="recipient",
            password="password"
        )

        self.expires_at = (
            timezone.now() + timedelta(days=7)
        )

    def create_test_invitation(self):

        return create_invitation(
            inviter=self.inviter,
            purpose="Test",
            expires_at=self.expires_at,
            recipient=self.recipient,
        )

    def test_create_invitation(self):
        self.assertEqual(Invitation.objects.count(), 0)

        self.create_test_invitation()

        self.assertEqual(Invitation.objects.count(), 1)

    def test_revokes_existing_invitation_for_user_when_a_new_one_is_created(self):
        invitation1 = self.create_test_invitation()
        invitation2 = self.create_test_invitation()
        pass

    def test_accept_invitation(self):
        invitation = self.create_test_invitation()

        self.assertEqual(invitation.status, InvitationStatus.PENDING)

        accept_invitation(
            invitation=invitation,
            accepted_by=self.recipient,
            )

        invitation.refresh_from_db()

        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)

    def test_cannot_accept_already_accepted_invitation(self):
        invitation = self.create_test_invitation()
        invitation.status = InvitationStatus.ACCEPTED
        invitation.save(update_fields=["status"])

        with self.assertRaises(InvitationAlreadyAcceptedError):
            accept_invitation(
                invitation=invitation,
                accepted_by=self.recipient,
                )

    def test_cannot_accept_revoked_invitation(self):
        invitation = self.create_test_invitation()
        invitation.status = InvitationStatus.REVOKED
        invitation.save(update_fields=["status"])

        with self.assertRaises(InvitationRevokedError):
            accept_invitation(invitation=invitation)

    def test_cannot_accept_expired_invitation(self):
        invitation = self.create_test_invitation()
        invitation.status = InvitationStatus.EXPIRED
        invitation.save(update_fields=["status"])

        with self.assertRaises(InvitationExpiredError):
            accept_invitation(invitation=invitation)

    def test_revoke_invitation(self):
        invitation = self.create_test_invitation()
        revoke_invitation(invitation=invitation)

        invitation.refresh_from_db()

        self.assertEqual(invitation.status, InvitationStatus.REVOKED)
        self.assertIsNotNone(invitation.revoked_at)

    def test_expire_invitation(self):
        invitation = self.create_test_invitation()

        invitation.expires_at = timezone.now() - timedelta(days=1)

        invitation.save(update_fields=["expires_at"])

        invitation.refresh_from_db()

        expire_invitation(invitation=invitation)

        invitation.refresh_from_db()

        self.assertEqual(invitation.status, InvitationStatus.EXPIRED)
        self.assertIsNotNone(invitation.expired_at)

    def test_get_invitation_by_token(self):
        invitation = self.create_test_invitation()

        invitation_token =  invitation.token

        self.assertEqual(invitation, get_invitation_by_token(token=invitation_token))

    def test_raises_if_exception_does_not_exist(self):
        with self.assertRaises(InvitationDoesNotExistError):
            get_invitation_by_token(token="herekjskdjkaj8282828")

class InvitationEventTests(TestCase):
    def setUp(self):
        self.inviter = User.objects.create_user(
            username="testuser",
            password="password"
        )

    def create_test_invitation(self):
        return create_invitation(
            inviter=self.inviter,
            purpose="Test",
            expires_at=(timezone.now() + timedelta(days=7)),
            recipient_email="test@gmail.com",
        )

    @patch("invite.events.invitation_created.send")
    @patch("invite.events.get_event_handler", return_value=None)
    def test_created_event_is_emited(self, mock_event_handler, mock_send):

        with self.captureOnCommitCallbacks(execute=True):
            create_invitation(
                inviter=self.inviter,
                purpose="Test",
                expires_at=(timezone.now() + timedelta(days=7)),
                recipient_email="test@gmail.com",
            )

        mock_send.assert_called_once()

    @patch("invite.events.invitation_accepted.send")
    @patch("invite.events.get_event_handler", return_value=None)
    def test_accepted_event_emited(self, mock_get_event_handler, mock_send):
        invitation = self.create_test_invitation()

        with self.captureOnCommitCallbacks(execute=True):
            accept_invitation(invitation=invitation)

        mock_send.assert_called_once()

    @patch("invite.events.invitation_revoked.send")
    @patch("invite.events.get_event_handler", return_value=None)
    def test_revoked_event_emited(self, mock_get_event_handler, mock_send):
        invitation = self.create_test_invitation()

        with self.captureOnCommitCallbacks(execute=True):
            revoke_invitation(invitation=invitation)

        mock_send.assert_called_once()


    @patch("invite.events.invitation_expired.send")
    @patch("invite.events.get_event_handler", return_value=None)
    def test_expired_event_emited(self, mock_get_event_handler, mock_send):
        invitation = self.create_test_invitation()
        invitation.expires_at = timezone.now() - timedelta(days=1)

        invitation.save(update_fields=["expires_at"])

        invitation.refresh_from_db()

        with self.captureOnCommitCallbacks(execute=True):
            expire_invitation(invitation=invitation)
        
        mock_send.assert_called_once()
