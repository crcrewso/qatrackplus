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

from unittest import mock

from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse
from django.utils import translation


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
        """The reveal is the login page only, and stays that way.

        `_form.html` renders every form in QATrack+, so a reveal added there
        would appear on the admin's change-password form and anywhere else a
        password field is rendered. That is a wider change than this is, and it
        should be a deliberate one rather than a side effect of this.
        """
        source = get_template("_form.html").template.source
        assert "id_password" not in source and "aria-pressed" not in source, (
            "the reveal has leaked into _form.html, so it now appears on every "
            "form in QATrack+ rather than the login page"
        )

    def test_a_translated_label_keeps_its_quotes_and_cannot_break_the_script(self):
        """The labels go into a JavaScript string, and from there into the button's text.

        HTML-escaping them, which `{% trans %}` does by itself, kept the script valid but put
        `&quot;` on the button. They are JavaScript-escaped instead.
        """
        risky = 'Afficher le "mot de passe" </script>'

        def fake_gettext(message):
            return risky if message in ("Show password", "Hide password") else message

        with mock.patch.object(translation._trans, "gettext", fake_gettext, create=True):
            html = self.client.get(self.url).content.decode()

        assert risky not in html, "a translated label reached the script unescaped"
        assert "&quot;mot de passe&quot;" not in html, "the label was HTML-escaped, so the button would show &quot;"
        assert "\\u0022mot de passe\\u0022" in html, "the label was not written through escapejs"

