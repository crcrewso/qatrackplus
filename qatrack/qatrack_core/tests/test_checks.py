import pytest
from django.conf import global_settings
from django.test import TestCase, override_settings

from qatrack import settings as qatrack_settings
from qatrack.qatrack_core.checks import (
    _suspect_setting_names,
    check_unedited_placeholders,
)


class TestUneditedPlaceholders(TestCase):
    """The deploy templates ship obvious placeholders; `import *` cannot tell
    an unedited one from a deliberate value, so a check has to.

    EMAIL_ENABLED is pinned in the host-placeholder tests below rather than
    left to whatever the ambient configuration happens to be: test_settings.py
    turns email on, and a developer's own local_settings.py may still carry the
    template's EMAIL_HOST_PASSWORD placeholder, which would make W002 fire
    alongside the error under test.
    """

    @override_settings(ALLOWED_HOSTS=['XX.XXX.XXX.XX'], EMAIL_ENABLED=False)
    def test_allowed_hosts_placeholder_is_an_error(self):
        problems = check_unedited_placeholders(None)
        assert [p.id for p in problems] == ['qatrack.E002']
        assert 'ALLOWED_HOSTS' in problems[0].msg

    @override_settings(CSRF_TRUSTED_ORIGINS=['http://YOUR_HOST_NAME_HERE'],
                       EMAIL_ENABLED=False)
    def test_csrf_trusted_origins_placeholder_is_an_error(self):
        problems = check_unedited_placeholders(None)
        assert [p.id for p in problems] == ['qatrack.E002']
        assert 'CSRF_TRUSTED_ORIGINS' in problems[0].msg

    @override_settings(ALLOWED_HOSTS=['qatrack.example.org'],
                       CSRF_TRUSTED_ORIGINS=['https://qatrack.example.org'],
                       EMAIL_ENABLED=False)
    def test_edited_configuration_is_silent(self):
        assert check_unedited_placeholders(None) == []

    @override_settings(ALLOWED_HOSTS=['qatrack.example.org'],
                       CSRF_TRUSTED_ORIGINS=['https://qatrack.example.org'],
                       DEBUG=False, EMAIL_ENABLED=True,
                       EMAIL_HOST_PASSWORD='your_password_here')
    def test_example_password_warns_when_email_is_enabled(self):
        problems = check_unedited_placeholders(None)
        assert [p.id for p in problems] == ['qatrack.W002']

    @override_settings(ALLOWED_HOSTS=['qatrack.example.org'],
                       CSRF_TRUSTED_ORIGINS=['https://qatrack.example.org'],
                       DEBUG=False, EMAIL_ENABLED=False,
                       EMAIL_HOST_PASSWORD='your_password_here')
    def test_example_password_ignored_when_email_is_disabled(self):
        # The templates ship this value commented out alongside the rest of the
        # email block; an instance not sending email is not using it.
        assert check_unedited_placeholders(None) == []


class TestSuspectSettingNames(TestCase):
    """`from .local_settings import *` accepts any name silently, so a
    misspelling defines an unused constant and leaves the real setting at its
    default."""

    def setUp(self):
        self.known = {n for n in dir(global_settings) if n.isupper()}
        self.known |= {n for n in dir(qatrack_settings) if n.isupper()}

    def test_catches_near_miss_names(self):
        found = dict(_suspect_setting_names(
            {'TIMEZONE', 'ALLOWED_HOST', 'DEBUGG'}, self.known))
        assert found['TIMEZONE'] == 'TIME_ZONE'
        assert found['ALLOWED_HOST'] == 'ALLOWED_HOSTS'
        assert found['DEBUGG'] == 'DEBUG'

    def test_leaves_real_settings_alone(self):
        assert _suspect_setting_names({'TIME_ZONE', 'DEBUG'}, self.known) == []

    def test_leaves_unrelated_constants_alone(self):
        # Deployers may define their own helpers in local_settings.py. Those
        # have no near neighbour among real settings, so they stay silent.
        assert _suspect_setting_names(
            {'HOSPITAL_NAME', 'MY_CUSTOM_THING'}, self.known) == []


class TestMediaFolderPermissions(TestCase):
    """Coverage for check_media_folder_permissions - issue #846.

    These are stubs. The check has six distinct outcomes and none of them are
    exercised today; the tests added alongside the placeholder and typo checks
    deliberately covered only the new checks. Each stub names the branch it
    should drive and how, so whoever picks this up is not re-deriving it from
    the source.

    Note the awkward part, and the likely reason this went uncovered: most of
    these branches depend on filesystem *permissions*, not just paths. Making
    a directory genuinely unwritable needs a real chmod, and a test that runs
    as root - which CI containers often do - will still be able to write to
    it, so a naive chmod-based test silently passes without proving anything.
    Expect to need either a skipif for root, or mocking of os.access.
    """

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_media_root_unset_is_an_error(self):
        """MEDIA_ROOT empty or None -> "The Media folder is not configured",
        and the check returns immediately without inspecting anything else.
        override_settings(MEDIA_ROOT=None) should be enough."""

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_missing_media_root_is_an_error(self):
        """MEDIA_ROOT set but the directory absent -> "does not exist", and
        again an early return. Point it at a tmp_path child that was never
        created."""

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_unwritable_uploads_dir_is_an_error(self):
        """An uploads directory that exists but is not writable -> Error
        carrying the chown/chmod hint. This is the branch most worth having,
        since it is the one a real deployment hits. See the note above about
        running as root."""

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_uploads_path_that_is_a_file_is_an_error(self):
        """`not directory.is_dir()` - something exists at the uploads path but
        is a regular file. Distinct from the unwritable case and currently
        shares its error branch; worth asserting separately so a future split
        of the two does not go unnoticed."""

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_uncreatable_uploads_dir_is_an_error(self):
        """The uploads directory does not exist and cannot be created ->
        Error with the "Check folder permissions and disk space." hint. Drive
        it by making the parent unwritable."""

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_unwritable_parent_is_an_error(self):
        """Parent exists but is not writable, so the directory could not be
        created later -> Error with the chown hint. Separate from the branch
        above: this one fires without attempting creation."""

    @pytest.mark.skip(reason="stub - not yet implemented")
    def test_healthy_media_tree_is_silent(self):
        """The case that should hold on every developer machine: MEDIA_ROOT
        and its uploads/tmp children exist and are writable -> no errors.
        Worth having explicitly, so a regression that makes the check noisy
        for everyone is caught rather than tolerated."""
