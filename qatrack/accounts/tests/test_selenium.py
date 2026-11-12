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

# As in test_ldap_backend.py: python-ldap comes from the `dev` group and is
# imported plainly, so its absence fails loudly instead of skipping.
import ldap  # noqa: E402,F401
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
        self.assert_signed_in_as("jdoe")

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


@pytest.mark.selenium
@override_settings(
    # Both backends, which is what a site running AD actually has: the shipped
    # AUTHENTICATION_BACKENDS lists QATrackAccountBackend with the AD backend
    # commented out below it. The local one is needed here because the account
    # created half way through this test has to be able to sign in.
    AUTHENTICATION_BACKENDS=[
        "qatrack.accounts.backends.QATrackAccountBackend",
        "qatrack.accounts.backends.ActiveDirectoryGroupMembershipSSLBackend",
    ],
    AD_NT4_DOMAIN="EXAMPLE",
    AD_SEARCH_DN="DC=example,DC=com",
    AD_LDAP_URL="ldap://ad.example.com:389",
    AD_CLEAN_USERNAME=None,
    AD_CLEAN_USERNAME_STRING="",
    CLEAN_USERNAME_STRING="",
    AD_CERT_FILE="",
    AD_MIRROR_GROUPS=False,
)
class TestMakingTheLocalSideDoor(BaseQATests):
    """An AD administrator creates a local account, and it works when AD does not.

    The side door sites rely on is an account QATrack+ holds itself, for the
    day the directory is unreachable. `test_ldap_backend.py` covers that such
    an account authenticates; this covers how one comes to exist, which is the
    half nobody can do from a settings file: an administrator signs in, adds
    the user through the Django admin, and that account is then a way back in.

    The whole sequence, in one test, because it is one claim and the steps are
    only meaningful in order:

    1. an AD account with admin rights signs in through the real login form,
       against a directory that is up;
    2. it creates a local user through `/admin/auth/user/add/`, typing a
       password, the way an administrator does;
    3. it signs out;
    4. the new account signs in through the real login form **with the
       directory down** - which is the point of the whole exercise.

    **How the AD account comes to have admin rights is worth knowing**, and is
    set up rather than asserted here. `get_or_create_user()` creates an AD
    account with `is_staff=False, is_superuser=False`, and
    `update_user_attributes()` never touches either flag - group mapping cannot
    grant them, because they are user flags and not permissions. So a fresh AD
    site has no administrator at all until a *local* superuser - the one
    `createsuperuser` makes during the install - grants staff to somebody. The
    row is pre-created here with those flags, which is the state after an
    administrator has done that, and is also why the install's local superuser
    matters more than it looks.
    """

    AD_PASSWORD = "s3cret-directory-password"
    NEW_PASSWORD = "Quarterly-Bremsstrahlung-74"

    def setUp(self):
        super().setUp()

        # The AD account, already granted admin rights by a local superuser -
        # see the class docstring. No usable password: its credentials live in
        # the directory, and this is what stops it being a side door itself.
        self.ad_admin = User.objects.create(
            username="ad-admin", email="ad-admin@example.com",
            is_staff=True, is_superuser=True, is_active=True,
        )
        self.ad_admin.set_unusable_password()
        self.ad_admin.save()

        self.directory_user = FakeUser(
            "ad-admin", self.AD_PASSWORD,
            email="ad-admin@example.com", surname="Admin", given_name="Ada",
        )

    def directory(self, **kwargs):
        return FakeDirectory([self.directory_user], settings=django_settings, **kwargs)

    def wait_for_the_logged_in_navbar(self, what):
        return self.wait.until(
            e_c.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="logout"]')),
            what,
        )

    def test_an_ad_admin_creates_a_local_account_that_works_when_ad_is_down(self):
        # 1. The AD administrator signs in, against a directory that answers.
        with self.directory().patch():
            self.submit_login_form("ad-admin", self.AD_PASSWORD)
            self.wait_for_the_logged_in_navbar(
                "the logged-in navbar after the AD administrator signed in")

        assert "/accounts/login/" not in self.driver.current_url, self.driver.current_url

        # 2. ...and creates a local user through the admin, as an administrator
        # does. Typed into the real form rather than created in the ORM: the
        # claim is that this route produces a usable account, and the admin's
        # add form is the route.
        self.open("/admin/auth/user/add/")
        self.wait.until(
            e_c.presence_of_element_located((By.CSS_SELECTOR, "#id_username")),
            "the admin's add-user form",
        )
        self.send_keys("id_username", "local-standby")
        self.send_keys("id_password1", self.NEW_PASSWORD)
        self.send_keys("id_password2", self.NEW_PASSWORD)
        self.driver.find_element(By.CSS_SELECTOR, 'input[name="_save"]').click()

        # The admin sends you to the new user's change form, so its username
        # field carrying the new name is the signal that the save went through.
        # Waiting on a success message alone would also match a validation
        # error page in some themes.
        # Not `#id_username`: the add form carries that field already, and so
        # does a re-rendered validation-error page, so the wait is satisfied
        # before the POST has finished and the query below can run against a
        # database the user has not been committed to yet. UserAdmin redirects
        # a saved add to the change form, so the URL is the signal that only
        # the post-save page gives.
        self.wait.until(
            e_c.url_contains("/change/"),
            "the new user's change form after saving",
        )

        created = User.objects.get(username="local-standby")
        assert created.has_usable_password(), (
            "the admin's add form produced an account with no usable password, "
            "which would make it useless as a way in"
        )
        assert not created.is_staff
        assert not created.is_superuser

        # 3. Sign out, by the link in the navbar rather than by URL - it is
        # what an administrator clicks, and it is the only thing that proves
        # the link works.
        #
        # Back to QATrack+ first. The Django admin has no logout link to
        # click: Django 4.1 made admin logout a POST form, which is also why
        # load_admin() waits on #user-tools rather than a logout href. The
        # navbar link is QATrack+'s own, on QATrack+'s own pages.
        self.open("")
        self.wait_for_the_logged_in_navbar("the QATrack+ navbar, back from the admin")
        self.click_by_css_selector('a[href*="logout"]')
        self.wait.until(
            e_c.presence_of_element_located((By.CSS_SELECTOR, "#id_username")),
            "the login form after signing out",
        )

        # 4. And the new account signs in with the directory unreachable.
        # This is the claim: an account created this way is a way back in on
        # the day AD is the thing that is broken.
        outage = self.directory(server_down=True)
        with outage.patch():
            self.submit_login_form("local-standby", self.NEW_PASSWORD)
            self.wait_for_the_logged_in_navbar(
                "the logged-in navbar for the local account, with the directory down")

        assert "/accounts/login/" not in self.driver.current_url, self.driver.current_url
        self.assert_signed_in_as("local-standby")
        # The local backend is first, so a local account that authenticates
        # never reaches the directory at all. Asserted so that the outage in
        # this step is known to be irrelevant rather than assumed to be.
        assert outage.initialize_calls == [], outage.initialize_calls
