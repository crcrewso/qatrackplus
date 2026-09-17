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
