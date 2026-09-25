"""Tests for scripts/settings_report.py and the registry behind it.

Two things are being protected here. The report gets pasted into public
issue trackers, so the redaction tests are the important ones: a regression
there leaks a clinic's credentials. The registry tests are the second half -
a hand-maintained table of "what changed" is worthless once it drifts from
the tree, so each entry is checked against the source it describes.
"""

import ast
import os

from django.test import SimpleTestCase

from qatrack.qatrack_core.settings_registry import (
    DRIFTED,
    REMOVED,
    RENAMED,
    UNDECLARED_BUT_READ,
    classify,
)
from scripts import settings_report

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
SETTINGS_PY = os.path.join(ROOT, 'qatrack', 'settings.py')

SECRETS = {
    'secret_key': 'zzz-secret-key-value-do-not-leak-1234567890',
    'db_password': 'zzz-db-password-do-not-leak',
    'db_host': 'zzz-db-host.internal.example.org',
    'ldap_pw': 'zzz-ldap-bind-password',
    'email_pw': 'zzz-email-password',
    'path': '/home/zzzuser/qatrack/logs',
    'admin_email': 'zzz.person@hospital.example.org',
}

MESSY = """
SECRET_KEY = '{secret_key}'
ADMINS = (('Someone', '{admin_email}'),)
EMAIL_HOST_PASSWORD = '{email_pw}'
AD_LDAP_PW = '{ldap_pw}'
LOG_ROOT = '{path}'
ALLOWED_HOSTS = ['XX.XXX.XXX.XX']
TIME_ZONE = 'YOUR_TIME_ZONE_GOES_HERE'
TIMEZONE = 'America/Halifax'
CLEAN_USERNAME_STRING = 'DOMAIN\\\\'
UPLOADS_URL = '/media/uploads/'
BACKUP_DIR = 'D:/backups'
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'qatrackplus',
        'USER': 'qatrack',
        'PASSWORD': '{db_password}',
        'HOST': '{db_host}',
    }}
}}
""".format(**SECRETS)


def write(tmpdir, text, name='local_settings.py'):
    path = os.path.join(tmpdir, name)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    return path


class TestRedaction(SimpleTestCase):
    """The report is meant to be pasted in public. Nothing secret may survive."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.report = settings_report.build_report(
            write(self.tmp, MESSY), SETTINGS_PY,
        )

    def test_no_secret_value_appears_anywhere(self):
        for label, value in SECRETS.items():
            assert value not in self.report, "%s leaked into the report" % label

    def test_secret_names_are_still_listed(self):
        # Hiding the value must not hide the fact that the setting is set -
        # knowing SECRET_KEY is defined is diagnostic, knowing its value is not.
        for name in ('SECRET_KEY', 'AD_LDAP_PW', 'EMAIL_HOST_PASSWORD'):
            assert '`%s`' % name in self.report

    def test_hidden_values_are_fingerprinted(self):
        assert settings_report.fingerprint('abc') == settings_report.fingerprint('abc')
        assert settings_report.fingerprint('abc') != settings_report.fingerprint('abd')
        assert len(settings_report.fingerprint('abc')) == 8

    def test_database_password_and_host_are_hidden_but_engine_shown(self):
        assert 'django.db.backends.postgresql' in self.report
        assert SECRETS['db_password'] not in self.report
        assert SECRETS['db_host'] not in self.report

    def test_computed_values_are_not_rendered(self):
        # A path built with os.path.join carries an account name.
        node = ast.parse("X = os.path.join('/home/zzzuser', 'logs')").body[0].value
        rendered, fp = settings_report.describe('LOG_ROOT', node)
        assert 'zzzuser' not in rendered

    def test_unknown_setting_with_secret_value_is_hidden(self):
        # The allowlist must be a default-deny: a name nobody anticipated
        # still gets its value hidden.
        node = ast.parse("X = 'zzz-invented-site-token'").body[0].value
        rendered, fp = settings_report.describe('SITE_SPECIFIC_TOKEN', node)
        assert 'zzz-invented-site-token' not in rendered
        assert 'hidden' in rendered


class TestFindings(SimpleTestCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.report = settings_report.build_report(
            write(self.tmp, MESSY), SETTINGS_PY,
        )

    def test_flags_removed_renamed_and_drifted(self):
        assert 'removed in' in self.report            # UPLOADS_URL
        assert 'ACCOUNTS_CLEAN_USERNAME_STRING' in self.report  # rename target
        assert 'meaning changed in' in self.report    # TIME_ZONE
        assert 'still honoured' in self.report        # BACKUP_DIR

    def test_flags_unedited_placeholders(self):
        assert 'unedited placeholder' in self.report
        assert 'YOUR_TIME_ZONE_GOES_HERE' in self.report

    def test_flags_probable_typo(self):
        assert 'possible typo' in self.report
        assert '`TIMEZONE`' in self.report

    def test_missing_time_zone_is_called_out(self):
        report = settings_report.build_report(
            write(self.tmp, "DEBUG = False\n", 'other.py'), SETTINGS_PY,
        )
        assert 'not set' in report and 'TIME_ZONE' in report

    def test_syntax_error_reports_a_line_number(self):
        report = settings_report.build_report(
            write(self.tmp, "DEBUG = (\n", 'broken.py'), SETTINGS_PY,
        )
        assert 'syntax error on line' in report

    def test_missing_file_is_not_a_crash(self):
        report = settings_report.build_report(
            os.path.join(self.tmp, 'nope.py'), SETTINGS_PY,
        )
        assert 'Could not read the file' in report

    def test_nothing_is_executed(self):
        # If the file were imported, this would raise.
        path = write(self.tmp, "raise SystemExit('should never run')\nDEBUG = True\n", 'boom.py')
        settings_report.build_report(path, SETTINGS_PY)


class TestRunsWithoutDjango(SimpleTestCase):

    def test_script_imports_no_django(self):
        """The deployments that need this most are the ones Django cannot start."""
        with open(settings_report.__file__.replace('.pyc', '.py'), encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split('.')[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
        assert 'django' not in imported

    def test_registry_imports_nothing(self):
        from qatrack.qatrack_core import settings_registry
        with open(settings_registry.__file__, encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        assert not [n for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)]


class TestRegistryMatchesTheTree(SimpleTestCase):
    """Stop the hand-maintained tables from rotting."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.declared, _ = settings_report.parse_assignments(SETTINGS_PY)

    def test_removed_names_are_really_gone(self):
        for name in REMOVED:
            assert name not in self.declared, "%s is still declared in settings.py" % name

    def test_renamed_old_gone_and_new_present(self):
        for old, detail in RENAMED.items():
            assert old not in self.declared, "%s is still declared" % old
            assert detail['new'] in self.declared, "%s is not declared" % detail['new']

    def test_undeclared_but_read_are_absent_here_and_read_there(self):
        for name, detail in UNDECLARED_BUT_READ.items():
            assert name not in self.declared, "%s IS declared; drop it from the table" % name
            with open(os.path.join(ROOT, detail['read_by']), encoding='utf-8') as fh:
                assert name in fh.read(), "%s not read by %s" % (name, detail['read_by'])

    def test_drifted_names_still_exist(self):
        for name in DRIFTED:
            assert name in self.declared, "%s no longer exists; it was removed, not drifted" % name

    def test_no_name_is_in_two_tables(self):
        seen = []
        for table in (REMOVED, RENAMED, UNDECLARED_BUT_READ, DRIFTED):
            seen.extend(table)
        assert len(seen) == len(set(seen))

    def test_classify_covers_every_entry(self):
        for table in (REMOVED, RENAMED, UNDECLARED_BUT_READ, DRIFTED):
            for name in table:
                assert classify(name)[0] is not None

    def test_known_placeholders_still_appear_in_the_repo(self):
        """A placeholder we no longer ship is a false positive waiting to happen."""
        import subprocess
        for placeholder in settings_report.KNOWN_PLACEHOLDERS:
            hits = subprocess.run(
                ['git', 'grep', '-l', '-F', placeholder, '--', 'qatrack/settings.py', 'deploy/'],
                cwd=ROOT, capture_output=True, text=True,
            ).stdout.strip()
            assert hits, "%r is no longer anywhere in the repo" % placeholder


class TestTimeZoneGuard(SimpleTestCase):
    """settings.py refuses to start on an unusable TIME_ZONE.

    Django's own validation is skipped wherever time.tzset() is missing, so on
    Windows the placeholder used to survive startup and fail later, at the
    first request that formatted a date.
    """

    def setUp(self):
        from unittest import mock

        from django.core.exceptions import ImproperlyConfigured

        from qatrack import settings as settings_module

        self.mock = mock
        self.module = settings_module
        self.error = ImproperlyConfigured

    def check(self, value):
        with self.mock.patch.object(self.module, 'TIME_ZONE', value):
            self.module._check_time_zone()

    def test_placeholder_gets_its_own_message(self):
        # zoneinfo would reject the placeholder anyway, so this asserts on
        # wording unique to the placeholder branch - otherwise the test passes
        # even when that branch is removed.
        with self.assertRaises(self.error) as caught:
            self.check('YOUR_TIME_ZONE_GOES_HERE')
        message = str(caught.exception)
        assert 'still the placeholder' in message
        assert 'shifts due dates' in message
        assert 'local_settings.py' in message

    def test_unrecognised_name_gets_the_other_message(self):
        with self.assertRaises(self.error) as caught:
            self.check('Not/A/Zone')
        assert 'still the placeholder' not in str(caught.exception)

    def test_windows_style_name_is_rejected(self):
        with self.assertRaises(self.error) as caught:
            self.check('Eastern Standard Time')
        assert 'IANA' in str(caught.exception)

    def test_nonsense_name_is_rejected(self):
        with self.assertRaises(self.error):
            self.check('Not/A/Zone')

    def test_real_zones_are_accepted(self):
        for zone in ('America/Toronto', 'Europe/London', 'UTC', 'Australia/Sydney'):
            self.check(zone)

    def test_guard_does_not_depend_on_tzset(self):
        # The whole point: it must reach the same verdict where Django's
        # check is skipped, which is how Windows behaves.
        with self.mock.patch('time.tzset', create=True, side_effect=AttributeError):
            with self.assertRaises(self.error):
                self.check('YOUR_TIME_ZONE_GOES_HERE')
