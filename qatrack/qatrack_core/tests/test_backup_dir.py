"""``BACKUP_DIR`` must not send a Linux site's backups into a folder called ``C:\\deploy\\backups``.

4.0.2 shipped the Windows path as the default on every platform. On Linux that is a
relative path, so ``backup_site`` created a folder of that literal name inside the
checkout and reported success (the 2026-10-29 upgrade walk found it; aviary B175).
"""

import os
import unittest

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from qatrack.qatrack_core import checks


class TestTheDefault(SimpleTestCase):

    def test_default_matches_the_platform(self):
        if os.name == 'nt':
            assert settings.BACKUP_DIR == "C:\\deploy\\backups"
        else:
            assert settings.BACKUP_DIR == os.path.join(settings.BASE_DIR, "backups")
            assert os.path.isabs(settings.BACKUP_DIR)


@unittest.skipIf(os.name == 'nt', "the warning is for hosts that are not Windows")
class TestWindowsPathOnLinuxWarns(SimpleTestCase):

    @override_settings(BACKUP_DIR="C:\\deploy\\backups")
    def test_the_old_default_is_reported(self):
        warnings = checks.check_backup_dir(None)
        assert [w.id for w in warnings] == ['qatrack.W016']
        assert "C:\\\\deploy\\\\backups" in warnings[0].msg or "C:\\deploy\\backups" in warnings[0].msg
        assert "local_settings.py" in warnings[0].hint

    @override_settings(BACKUP_DIR="D:/backups/qatrack")
    def test_a_forward_slash_drive_path_is_reported_too(self):
        assert [w.id for w in checks.check_backup_dir(None)] == ['qatrack.W016']

    @override_settings(BACKUP_DIR="/var/backups/qatrackplus")
    def test_a_posix_path_is_quiet(self):
        assert checks.check_backup_dir(None) == []

    @override_settings(BACKUP_DIR="backups")
    def test_a_relative_posix_path_is_quiet(self):
        """Odd, but not the defect this check is for."""
        assert checks.check_backup_dir(None) == []
