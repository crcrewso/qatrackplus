"""Links into the manual follow the release line the site is running.

The footer of a 4.0.2 site pointed at ``/en/3.1.0/user/guide.html`` over plain
http, and an admin page at ``/en/latest/``, which does not resolve on this
project's Read the Docs. ``DOCS_URL`` is derived from ``VERSION`` instead
(aviary B181).
"""

import pathlib

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from qatrack.qa.tests import utils


class TestDocsUrl(SimpleTestCase):

    def test_follows_the_release_line(self):
        major_minor = ".".join(settings.VERSION.split(".")[:2])
        assert settings.DOCS_URL == "https://docs.qatrackplus.com/en/releases-%s/" % major_minor

    def test_no_template_pins_a_version(self):
        offenders = []
        for path in pathlib.Path(settings.PROJECT_ROOT).rglob("*.html"):
            if "docs.qatrackplus.com/en/" in path.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(str(path))
        assert offenders == [], offenders


class TestFooterLink(TestCase):

    def test_the_footer_links_this_release_line(self):
        self.client.force_login(utils.create_user())
        html = self.client.get(reverse("home")).content.decode("UTF-8")
        assert settings.DOCS_URL + "user/guide.html" in html
        assert "docs.qatrackplus.com/en/3.1.0" not in html
