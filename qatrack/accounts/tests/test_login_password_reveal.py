"""The login page's "show password" control.

Only Edge renders a reveal control of its own, so on Chrome, Firefox and Safari
a mistyped password is invisible and there is no browser setting to change that.
This covers the login page alone - the one field where somebody types a password
they were handed rather than one their browser fills.

**What these tests can and cannot say.** They ask the real view for the real
page, so they establish that the control is wired up and that the field is still
a password field when it arrives. They cannot click it: flipping `type` and
moving focus is browser behaviour, and belongs in a Selenium test. Stated here
so the next reader does not take a green run as proof the toggle works.
"""

import os

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class TestTheLoginPageOffersToRevealThePassword(TestCase):

    def setUp(self):
        self.url = reverse("login")

    def test_the_page_renders(self):
        assert self.client.get(self.url).status_code == 200

    def test_the_password_field_arrives_hidden(self):
        """A reveal that defaulted to visible would be worse than none."""
        html = self.client.get(self.url).content.decode()
        assert 'type="password"' in html, (
            "the login page has no password field, so either the form changed or "
            "something is rendering it as plain text"
        )
        assert 'id="id_password"' in html, (
            "the password field is not #id_password, which is what the toggle "
            "attaches to - the toggle will silently do nothing"
        )

    def test_the_toggle_is_wired_to_that_field(self):
        html = self.client.get(self.url).content.decode()
        assert '#id_password' in html, (
            "nothing on the login page references #id_password, so the reveal "
            "control was dropped"
        )
        assert 'aria-pressed' in html, (
            "the toggle does not report its state, so a screen reader announces a "
            "button that appears to do nothing"
        )

    def test_the_toggle_does_not_submit_the_form(self):
        """A bare <button> inside a form defaults to type=submit."""
        html = self.client.get(self.url).content.decode()
        assert 'type: "button"' in html or "type: 'button'" in html, (
            "the reveal button does not set type=button. Inside a form a button "
            "defaults to submit, so clicking it would post the login form"
        )

    def test_the_shared_form_partial_is_untouched(self):
        """This is the login page only, by Cody's decision 2026-11-11.

        `_form.html` renders every form in QATrack+; a reveal added there would
        appear on the admin's change-password form and anywhere else a password
        field is rendered, which was not what was asked for.
        """
        partial = os.path.join(settings.PROJECT_ROOT, "templates", "_form.html")
        with open(partial, encoding="utf-8") as f:
            source = f.read()
        assert "id_password" not in source and "aria-pressed" not in source, (
            "the reveal has leaked into _form.html, so it now appears on every "
            "form in QATrack+ rather than the login page"
        )
