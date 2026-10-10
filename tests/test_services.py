from django.test import TestCase, SimpleTestCase
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from invite.conf import SETTING_NAME, get_settings, get_event_handler
from invite.models import Invitation, InvitationStatus
from django.utils import timezone
from invite.exceptions import InvitationAlreadyAcceptedError, InvitationCallbackNotCallable, InvitationDoesNotExistError, InvitationError, InvitationExpiredError, InvitationRevokedError, MaximumTTLExceededError
from invite.services import create_invitation, accept_invitation, get_invitation_by_token, hash_token, revoke_invitation, expire_invitation, rotate_token

User = get_user_model()

def invitation_create():
    return

NOT_COLLABLE = "invitation_create"

class SettingsConfTestCase(SimpleTestCase):
    def test_returns_settings_dict(self):
        settings = {
            "INVITE_CREATED_CALLBACK": "tests.test_services.invitation_create",
            "INVITE_ACCEPTED_CALLBACK": None,
            "INVITE_REVOKED_CALLBACK": None,
            "INVITE_EXPIRED_CALLBACK": None,
            "MAX_TTL": 7 * 24 * 60 * 60,
            "REQUIRE_EMAIL_MATCH": True
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

    @patch("invite.conf.get_settings", return_value={"INVITE_CREATED_CALLBACK": "tests.test_services.invitation_create"})
    def test_gets_the_right_handler(self, mock_settings_get):

        self.assertEqual(invitation_create, get_event_handler("INVITE_CREATED_CALLBACK"))

    @patch("invite.conf.get_settings", return_value={"INVITE_CREATED_CALLBACK": "tests.test_services.NOT_COLLABLE"})
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
            timezone.now() + timezone.timedelta(days=7)
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

    def test_create_returns_raw_token(self):
        invitation = create_invitation(
            inviter=self.inviter,
            purpose="Test",
            expires_at=self.expires_at,
            recipient=self.recipient,
        )

        self.assertIsNotNone(invitation.raw_token)

    def test_sets_default_expires_at(self):
        before = timezone.now()

        invitation = create_invitation(
            inviter=self.inviter,
            purpose="Test",
            recipient=self.recipient,
        )

        after = timezone.now()

        max_ttl = get_settings().get("MAX_TTL")

        expected_earliest = before + timezone.timedelta(seconds=max_ttl)
        expected_latest = after + timezone.timedelta(seconds=max_ttl)

        self.assertGreaterEqual(invitation.expires_at, expected_earliest)
        self.assertLessEqual(invitation.expires_at, expected_latest)

    def test_raises_if_expires_at_is_greater_than_MAX_TTL(self):

        with self.assertRaises(MaximumTTLExceededError):
            invitation = create_invitation(
                inviter=self.inviter,
                purpose="Test",
                expires_at=timezone.now() + timezone.timedelta(days=10),
                recipient=self.recipient,
            )



    def test_create_invitation_does_not_save_raw_token(self):
        invitation = create_invitation(
            inviter=self.inviter,
            purpose="Test",
            expires_at=self.expires_at,
            recipient=self.recipient,
        )

        self.assertNotEqual(invitation.raw_token, invitation.token_hash)

    def test_accept_invitation(self):
        invitation = self.create_test_invitation()

        self.assertEqual(invitation.status, InvitationStatus.PENDING)

        accept_invitation(
            token=invitation.raw_token,
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
                token=invitation.raw_token,
                accepted_by=self.recipient,
                )

    def test_cannot_accept_revoked_invitation(self):
        invitation = self.create_test_invitation()
        invitation.status = InvitationStatus.REVOKED
        invitation.save(update_fields=["status"])

        with self.assertRaises(InvitationRevokedError):
            accept_invitation(token=invitation.raw_token)

    def test_cannot_accept_expired_invitation(self):
        invitation = self.create_test_invitation()
        invitation.status = InvitationStatus.EXPIRED
        invitation.save(update_fields=["status"])

        with self.assertRaises(InvitationExpiredError):
            accept_invitation(token=invitation.raw_token)

    def test_revoke_invitation(self):
        invitation = self.create_test_invitation()
        revoke_invitation(invitation=invitation)

        invitation.refresh_from_db()

        self.assertEqual(invitation.status, InvitationStatus.REVOKED)
        self.assertIsNotNone(invitation.revoked_at)

    def test_expire_invitation(self):
        invitation = self.create_test_invitation()

        invitation.expires_at = timezone.now() - timezone.timedelta(days=1)

        invitation.save(update_fields=["expires_at"])

        invitation.refresh_from_db()

        expire_invitation(invitation=invitation)

        invitation.refresh_from_db()

        self.assertEqual(invitation.status, InvitationStatus.EXPIRED)
        self.assertIsNotNone(invitation.expired_at)

    def test_get_invitation_by_raw_token(self):
        invitation = self.create_test_invitation()

        invitation_token =  invitation.raw_token

        self.assertEqual(invitation, get_invitation_by_token(token=invitation_token))

    def test_get_invitation_by_token(self):
        invitation = self.create_test_invitation()

        invitation_token =  invitation.token_hash

        self.assertEqual(invitation, get_invitation_by_token(token=invitation_token, is_raw=False))

    def test_raises_if_exception_does_not_exist(self):
        with self.assertRaises(InvitationDoesNotExistError):
            get_invitation_by_token(token="herekjskdjkaj8282828")

    def test_rotate_token_returns_new_raw_token(self):
        invitation = self.create_test_invitation()
        old_raw_token = invitation.raw_token

        rotated = rotate_token(invitation=invitation)

        self.assertIsNotNone(rotated.raw_token)
        self.assertNotEqual(rotated.raw_token, old_raw_token)

    def test_rotate_token_stores_new_hash(self):
        invitation = self.create_test_invitation()
        old_hash = invitation.token_hash

        rotated = rotate_token(invitation=invitation)

        invitation.refresh_from_db()

        self.assertNotEqual(invitation.token_hash, old_hash)
        self.assertEqual(invitation.token_hash, hash_token(rotated.raw_token))

    def test_old_token_does_not_work_after_rotation(self):
        invitation = self.create_test_invitation()
        old_raw_token = invitation.raw_token

        rotate_token(invitation=invitation)

        with self.assertRaises(InvitationDoesNotExistError):
            get_invitation_by_token(token=old_raw_token)

    def test_new_token_works_after_rotation(self):
        invitation = self.create_test_invitation()

        rotated = rotate_token(invitation=invitation)

        self.assertEqual(invitation, get_invitation_by_token(token=rotated.raw_token))

    def test_can_accept_invitation_with_rotated_token(self):
        invitation = self.create_test_invitation()

        rotated = rotate_token(invitation=invitation)

        accept_invitation(
            token=rotated.raw_token,
            accepted_by=self.recipient,
        )

        invitation.refresh_from_db()

        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)

    def test_rotate_token_keeps_status_and_expires_at(self):
        invitation = self.create_test_invitation()
        expires_at = invitation.expires_at

        rotate_token(invitation=invitation)

        invitation.refresh_from_db()

        self.assertEqual(invitation.status, InvitationStatus.PENDING)
        self.assertEqual(invitation.expires_at, expires_at)

    def test_cannot_rotate_accepted_invitation(self):
        invitation = self.create_test_invitation()
        invitation.status = InvitationStatus.ACCEPTED
        invitation.save(update_fields=["status"])

        with self.assertRaises(InvitationAlreadyAcceptedError):
            rotate_token(invitation=invitation)

    def test_cannot_rotate_revoked_invitation(self):
        invitation = self.create_test_invitation()
        invitation.status = InvitationStatus.REVOKED
        invitation.save(update_fields=["status"])

        with self.assertRaises(InvitationRevokedError):
            rotate_token(invitation=invitation)

    def test_cannot_rotate_expired_invitation(self):
        invitation = self.create_test_invitation()
        invitation.status = InvitationStatus.EXPIRED
        invitation.save(update_fields=["status"])

        with self.assertRaises(InvitationExpiredError):
            rotate_token(
                invitation=invitation,
                expires_at=timezone.now() + timezone.timedelta(days=1),
            )

    def test_cannot_rotate_invitation_that_expired_by_time(self):
        invitation = self.create_test_invitation()
        invitation.expires_at = timezone.now() - timezone.timedelta(days=1)
        invitation.save(update_fields=["expires_at"])

        with self.assertRaises(InvitationExpiredError):
            rotate_token(invitation=invitation)

    def test_rotate_token_can_revive_invitation_that_expired_by_time(self):
        invitation = self.create_test_invitation()
        invitation.expires_at = timezone.now() - timezone.timedelta(days=1)
        invitation.save(update_fields=["expires_at"])

        new_expires_at = timezone.now() + timezone.timedelta(days=3)

        rotated = rotate_token(invitation=invitation, expires_at=new_expires_at)

        invitation.refresh_from_db()

        self.assertEqual(invitation.expires_at, new_expires_at)
        self.assertTrue(invitation.is_valid)
        self.assertIsNotNone(rotated.raw_token)

    def test_rotate_token_raises_if_expires_at_is_in_the_past(self):
        invitation = self.create_test_invitation()

        with self.assertRaises(InvitationError):
            rotate_token(
                invitation=invitation,
                expires_at=timezone.now() - timezone.timedelta(minutes=1),
            )

    def test_rotate_token_raises_if_expires_at_exceeds_max_ttl(self):
        invitation = self.create_test_invitation()
        max_ttl = get_settings().get("MAX_TTL")

        with self.assertRaises(MaximumTTLExceededError):
            rotate_token(
                invitation=invitation,
                expires_at=timezone.now() + timezone.timedelta(seconds=max_ttl + 3600),
            )

    def test_rotate_token_does_not_change_hash_when_it_fails(self):
        invitation = self.create_test_invitation()
        old_hash = invitation.token_hash
        invitation.status = InvitationStatus.REVOKED
        invitation.save(update_fields=["status"])

        with self.assertRaises(InvitationRevokedError):
            rotate_token(invitation=invitation)

        invitation.refresh_from_db()

        self.assertEqual(invitation.token_hash, old_hash)

    def test_rotate_token_checks_current_status_not_stale_instance(self):
        invitation = self.create_test_invitation()

        stale_invitation = Invitation.objects.get(pk=invitation.pk)
        revoke_invitation(invitation=invitation)

        self.assertEqual(stale_invitation.status, InvitationStatus.PENDING)

        with self.assertRaises(InvitationRevokedError):
            rotate_token(invitation=stale_invitation)

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
            expires_at=(timezone.now() + timezone.timedelta(days=7)),
            recipient_email="test@gmail.com",
        )

    @patch("invite.events.invitation_created.send")
    @patch("invite.events.get_event_handler", return_value=None)
    def test_created_event_is_emited(self, mock_event_handler, mock_send):

        with self.captureOnCommitCallbacks(execute=True):
            create_invitation(
                inviter=self.inviter,
                purpose="Test",
                expires_at=(timezone.now() + timezone.timedelta(days=7)),
                recipient_email="test@gmail.com",
            )

        mock_send.assert_called_once()

    @patch("invite.events.invitation_accepted.send")
    @patch("invite.events.get_event_handler", return_value=None)
    def test_accepted_event_emited(self, mock_get_event_handler, mock_send):
        invitation = self.create_test_invitation()

        with self.captureOnCommitCallbacks(execute=True):
            accept_invitation(token=invitation.raw_token)

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
        invitation.expires_at = timezone.now() - timezone.timedelta(days=1)

        invitation.save(update_fields=["expires_at"])

        invitation.refresh_from_db()

        with self.captureOnCommitCallbacks(execute=True):
            expire_invitation(invitation=invitation)
        
        mock_send.assert_called_once()
