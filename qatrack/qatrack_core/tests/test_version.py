"""The release version is written in two places by hand and must agree.

``qatrack/settings.py`` carries ``VERSION`` (what the footer, the admin and
``docs/conf.py`` show) and ``pyproject.toml`` carries ``version`` (what the
package and ``uv.lock`` say). Nothing derived one from the other, and nothing
compared them, so a release could report itself as one version in the browser
and another to pip (aviary B160; measured 2026-10-27 on three upstream branches
all reporting 4.0.1 in the footer while ``git describe`` disagreed).
"""

import pathlib
import tomllib

from django.conf import settings
from django.test import SimpleTestCase

ROOT = pathlib.Path(settings.BASE_DIR)


class TestTheVersionAgrees(SimpleTestCase):

    def test_pyproject_matches_settings(self):
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        assert pyproject["project"]["version"] == settings.VERSION, (
            "pyproject.toml says %s, qatrack/settings.py says %s - bump both when releasing"
            % (pyproject["project"]["version"], settings.VERSION)
        )

    def test_lockfile_matches_settings(self):
        """uv.lock records the project's own version; a bump without re-locking leaves it behind."""
        lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
        ours = [p for p in lock["package"] if p["name"] == "qatrackplus"]
        assert len(ours) == 1, ours
        assert ours[0]["version"] == settings.VERSION, (
            "uv.lock says %s, qatrack/settings.py says %s - run `uv lock` after bumping pyproject.toml"
            % (ours[0]["version"], settings.VERSION)
        )
