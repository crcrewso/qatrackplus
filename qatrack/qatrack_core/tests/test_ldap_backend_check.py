"""An LDAP backend with no python-ldap must not fail silently.

`qatrack/accounts/backends.py` wraps `import ldap` in a bare
try/except ImportError, so a missing dependency is swallowed. The backend
class still loads and Django still lists it, and the only symptom is that
logging in stops working - on a clinical system, with no startup error to
point at.

It is reachable without a mistake: python-ldap ships only in the `mssql`
extra, so a PostgreSQL site that follows the install guide and then turns on
Active Directory has no ldap module and nothing to tell it so.
"""

import sys
from unittest import mock

from django.core.checks import Error
from django.test import SimpleTestCase, override_settings

from qatrack.qatrack_core.checks import (
    LDAP_DEPENDENT_BACKENDS,
    check_ldap_backend_dependencies,
)

MODEL_ONLY = ['qatrack.accounts.backends.QATrackAccountBackend']
AD_SSL = 'qatrack.accounts.backends.ActiveDirectoryGroupMembershipSSLBackend'
WIA = 'qatrack.accounts.backends.WindowsIntegratedAuthenticationBackend'


def without_ldap():
    """Make `import ldap` raise, whether or not it is installed here."""
    return mock.patch.dict(sys.modules, {'ldap': None})


class TestLdapBackendCheck(SimpleTestCase):

    @override_settings(AUTHENTICATION_BACKENDS=MODEL_ONLY)
    def test_silent_when_no_ldap_backend_is_configured(self):
        """The common case: ModelBackend only. Must never complain."""
        with without_ldap():
            assert check_ldap_backend_dependencies(None) == []

    @override_settings(AUTHENTICATION_BACKENDS=MODEL_ONLY + [AD_SSL])
    def test_errors_when_ldap_is_missing(self):
        with without_ldap():
            problems = check_ldap_backend_dependencies(None)
        assert len(problems) == 1
        assert isinstance(problems[0], Error)
        assert problems[0].id == 'qatrack.E003'

    @override_settings(AUTHENTICATION_BACKENDS=MODEL_ONLY + [AD_SSL])
    def test_silent_when_ldap_is_importable(self):
        with mock.patch.dict(sys.modules, {'ldap': mock.Mock()}):
            assert check_ldap_backend_dependencies(None) == []

    def test_every_ldap_dependent_backend_is_detected(self):
        for backend in LDAP_DEPENDENT_BACKENDS:
            with self.settings(AUTHENTICATION_BACKENDS=MODEL_ONLY + [backend]):
                with without_ldap():
                    problems = check_ldap_backend_dependencies(None)
                assert problems, "%s did not trigger the check" % backend

    @override_settings(AUTHENTICATION_BACKENDS=MODEL_ONLY + [AD_SSL, WIA])
    def test_names_the_configured_backends(self):
        with without_ldap():
            problems = check_ldap_backend_dependencies(None)
        assert len(problems) == 1, "one error listing both, not one each"
        assert AD_SSL in problems[0].msg
        assert WIA in problems[0].msg

    @override_settings(AUTHENTICATION_BACKENDS=MODEL_ONLY + [AD_SSL])
    def test_hint_gives_an_install_command_and_the_linux_caveat(self):
        with without_ldap():
            hint = check_ldap_backend_dependencies(None)[0].hint
        assert 'uv sync --extra' in hint
        assert 'libldap2-dev' in hint

    @override_settings(AUTHENTICATION_BACKENDS=[])
    def test_empty_backends_is_not_a_crash(self):
        with without_ldap():
            assert check_ldap_backend_dependencies(None) == []
