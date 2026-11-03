"""The Active Directory sign-in path, through the real login form.

The fast half of this coverage is in ``test_ldap_backend.py``, and nearly
everything is asserted there, because a browser case costs about a hundred
times as much. These two tests are the part only a browser can show: that
somebody typing a directory password into the login page ends up on a page
that is theirs, and that somebody the directory authenticates but QATrack+
refuses is told so on the form rather than silently admitted.

That distinction is the whole reason this file exists. ``backends.py`` drops a
user who binds successfully but belongs to no qualifying group, and what a
signed-in user can then see depends on the AD-group-to-QATrack+-group mapping -
so a test on ``authenticate()`` alone cannot show the page they land on.

**These tests deliberately drive the form.** The rest of the Selenium suite
authenticates by session with ``login()``, on purpose: typing a password brings
the browser's own credential dialogs into play, which WebDriver cannot see. The
login page is what these tests are *for*, so they are the exception, along with
``TestLoginPage`` in ``qatrack/qa/tests/test_selenium.py``. Anything that makes
the suite faster by not typing passwords should leave these alone.

See ``ldap_fake.py`` for what the stand-in directory does and does not prove.
"""

import pytest
from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.test.utils import override_settings
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as e_c

from qatrack.accounts import models
from qatrack.accounts.tests.ldap_fake import FakeDirectory, FakeUser
from qatrack.accounts.tests.utils import create_group
from qatrack.qa.tests.test_selenium import BaseQATests

# As in test_ldap_backend.py: python-ldap is an extra, and backends.py reads
# real constants and exception classes off the module.
ldap = pytest.importorskip("ldap")


@pytest.mark.selenium
@override_settings(
    # The AD backend is commented out of the shipped AUTHENTICATION_BACKENDS,
    # so a site that has not configured it is unaffected by any of this. Here
    # it is the only backend, which also means the local account that
    # BaseQATests.setUp creates cannot sign in - correct for these tests, and
    # the reason they never use login().
    AUTHENTICATION_BACKENDS=["qatrack.accounts.backends.ActiveDirectoryGroupMembershipSSLBackend"],
    AD_NT4_DOMAIN="EXAMPLE",
    AD_SEARCH_DN="DC=example,DC=com",
    AD_LDAP_URL="ldap://ad.example.com:389",
    AD_CLEAN_USERNAME=None,
    AD_CLEAN_USERNAME_STRING="",
    CLEAN_USERNAME_STRING="",
    AD_CERT_FILE="",
    AD_MIRROR_GROUPS=False,
)
class TestActiveDirectoryLogin(BaseQATests):

    def setUp(self):
        super().setUp()
        self.physics = create_group("Physics QC")
        mapping = models.ActiveDirectoryGroupMap.objects.create(
            ad_group="Physics",
            account_qualifier=True,
        )
        mapping.groups.add(self.physics)

        self.jdoe = FakeUser(
            "jdoe",
            "s3cret",
            email="jdoe@example.com",
            surname="Doe",
            given_name="Jane",
            groups=["Physics"],
        )

    def directory(self, *users):
        return FakeDirectory(users or [self.jdoe], settings=django_settings)

    def test_an_ad_user_signs_in_and_lands_on_a_page_of_their_own(self):
        """The whole path, end to end, with nothing in QATrack+ beforehand.

        No User row exists for jdoe when this starts. By the time the page has
        rendered, the directory has been bound, the account has been created
        from the directory's attributes, the AD group has been mapped to a
        QATrack+ group, and the browser is on a logged-in page - which is the
        sequence a site configuring AD for the first time depends on and which
        nothing exercised.
        """
        assert not User.objects.filter(username="jdoe").exists()

        with self.directory().patch():
            self.submit_login_form("jdoe", "s3cret")
            self.wait.until(
                e_c.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="logout"]')),
                "the logged-in navbar after signing in with a directory password",
            )

        assert "/accounts/login/" not in self.driver.current_url, self.driver.current_url

        # The account the directory caused to exist, and the group that decides
        # what it can do. Read after the browser has finished, so this asserts
        # the state a real session was built from rather than a parallel one.
        user = User.objects.get(username="jdoe")
        assert user.first_name == "Jane"
        assert user.email == "jdoe@example.com"
        assert list(user.groups.all()) == [self.physics]

    def test_a_user_in_no_qualifying_group_is_told_on_the_form(self):
        """Authenticated by the directory, refused by QATrack+.

        The backend returns None for a user outside every qualifying group, and
        a None from a backend is indistinguishable at the view from a bad
        password - so what the person sees is the ordinary form error. Worth a
        browser test because the alternative failure, which this would catch,
        is a refused user being let through to a page with no groups.
        """
        outsider = FakeUser("rsmith", "hunter2", groups=["Radiation"])

        with self.directory(outsider).patch():
            self.submit_login_form("rsmith", "hunter2")
            self.wait.until(
                e_c.presence_of_element_located((By.CSS_SELECTOR, 'div.alert-danger[role="alert"]')),
                "the login form's error box after a refused sign-in",
            )

        assert "/accounts/login/" in self.driver.current_url, self.driver.current_url
        # No session: the logged-in navbar is what force_login() and
        # login_through_form() both wait for, and it must not be here.
        assert self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="logout"]') == []
        # And no account, so a later sign-in cannot find one already made.
        assert not User.objects.filter(username="rsmith").exists()
