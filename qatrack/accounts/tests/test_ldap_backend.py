"""The Active Directory sign-in path, driven against a stand-in directory.

Before this file, ``ActiveDirectoryGroupMembershipSSLBackend`` had three tests,
all of them on ``clean_username()``. Nothing ran the bind, the user lookup, the
qualifying-group check, or the account and group membership that come out the
other end - so the eleven ``AD_*`` settings that configure it had no coverage at
all, and neither did the decision about whether somebody may sign in.

These are the fast half. The browser half - the login form, and what a signed-in
AD user actually lands on - is in ``qatrack/accounts/tests/test_selenium.py``.
Everything that can be asserted without a browser is asserted here, because the
browser costs about a hundred times as much per case.

See ``ldap_fake.py`` for what the stand-in does and does not prove.
"""

import pytest
from django.conf import settings as django_settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.test.utils import override_settings

from qatrack.accounts import models
from qatrack.accounts.backends import (
    ActiveDirectoryGroupMembershipSSLBackend as ADBackend,
)
from qatrack.accounts.tests.ldap_fake import FakeDirectory, FakeUser

# python-ldap is an extra, not a base dependency, and backends.py reads real
# constants and real exception classes off the module - see ldap_fake.py. Skips
# the whole module rather than erroring during collection when it is absent.
ldap = pytest.importorskip("ldap")


@override_settings(
    AD_NT4_DOMAIN="EXAMPLE",
    AD_SEARCH_DN="DC=example,DC=com",
    AD_LDAP_URL="ldap://ad.example.com:389",
    AD_CLEAN_USERNAME=None,
    AD_CLEAN_USERNAME_STRING="",
    CLEAN_USERNAME_STRING="",
    AD_CERT_FILE="",
    AD_MIRROR_GROUPS=False,
)
class ADTestCase(TestCase):
    """Shared fixtures and the one-attempt helper.

    The settings above are pinned rather than inherited because the shipped
    defaults are all empty strings - with AD_NT4_DOMAIN unset the bind DN comes
    out as "jdoe@", which proves nothing about what a configured site sends.
    """

    def setUp(self):
        self.jdoe = FakeUser(
            "jdoe",
            "s3cret",
            email="jdoe@example.com",
            surname="Doe",
            given_name="Jane",
            groups=["Physics"],
        )

    def attempt(self, username, password, users=None, **directory_kwargs):
        """One sign-in attempt. Returns ``(user_or_None, directory)``.

        The backend is constructed *inside* the patch, because its ``__init__``
        is where ``ldap.set_option`` is called - that is the only place
        AD_CERT_FILE is read, so a backend built outside the patch would make
        that setting untestable.
        """
        directory = FakeDirectory(
            users if users is not None else [self.jdoe],
            # The lazy settings object, so each FakeUser attribute lookup reads
            # whatever override_settings has in force at that moment.
            settings=django_settings,
            **directory_kwargs,
        )
        with directory.patch():
            backend = ADBackend()
            user = backend.authenticate(None, username=username, password=password)
        return user, directory


class TestBind(ADTestCase):

    def test_successful_bind_creates_the_account(self):
        user, directory = self.attempt("jdoe", "s3cret")

        assert user is not None
        assert user.username == "jdoe"
        assert user.email == "jdoe@example.com"
        assert user.first_name == "Jane"
        assert user.last_name == "Doe"
        # The directory is the authority for the password, so the local account
        # must not have one that could be used to sign in around it.
        assert not user.has_usable_password()
        # An AD account arrives with no staff or superuser rights whatever the
        # directory says; those are granted in QATrack+.
        assert not user.is_staff
        assert not user.is_superuser

    def test_the_bind_dn_is_username_at_domain(self):
        """The one assertion that shows what we send to the directory.

        AD_NT4_DOMAIN has no other observable effect, so without this nothing
        would notice it being dropped from the DN.
        """
        _, directory = self.attempt("jdoe", "s3cret")
        assert directory.connection.binds == [("jdoe@EXAMPLE", "s3cret")]

    def test_wrong_password_authenticates_nobody(self):
        before = User.objects.count()
        user, directory = self.attempt("jdoe", "wrong")

        assert user is None
        # Not merely "returns None": a failed bind must not leave an account
        # behind, because an account is what a later successful ModelBackend
        # login would find.
        assert User.objects.count() == before

    def test_an_unknown_username_authenticates_nobody(self):
        user, _ = self.attempt("nobody", "s3cret")
        assert user is None
        assert not User.objects.filter(username="nobody").exists()

    def test_an_empty_password_never_reaches_the_directory(self):
        """Checked before the bind, and worth asserting as *not reaching* it.

        Some directories treat a bind with an empty credential as an anonymous
        bind and return success, which would sign the user in as whoever they
        claimed to be. The backend returns early instead; this test fails if
        that early return is ever removed.
        """
        user, directory = self.attempt("jdoe", "")

        assert user is None
        assert directory.connections == []

    def test_an_unreachable_server_authenticates_nobody(self):
        user, _ = self.attempt("jdoe", "s3cret", server_down=True)
        assert user is None

    def test_the_connection_is_unbound_after_a_failed_bind(self):
        """The ``finally`` clause, which is easy to lose in a refactor.

        A leaked connection per failed sign-in attempt is the kind of thing
        that only shows up on a directory under load.
        """
        _, directory = self.attempt("jdoe", "wrong")
        assert directory.connection.unbound

    def test_the_connection_is_unbound_after_a_successful_bind(self):
        _, directory = self.attempt("jdoe", "s3cret")
        assert directory.connection.unbound


class TestUsernameCleaning(ADTestCase):
    """What gets sent to the directory, rather than what the form accepted.

    The three existing tests in ``test_accounts.py`` cover ``clean_username()``
    in isolation. These cover it in place: that the cleaned name is what reaches
    the bind DN and the search filter, which is the part a site configuring
    AD_CLEAN_USERNAME actually depends on.
    """

    @override_settings(AD_CLEAN_USERNAME=lambda username: username.lower())
    def test_a_clean_username_callable_reaches_the_bind(self):
        user, directory = self.attempt("JDoe", "s3cret")

        assert directory.connection.binds == [("jdoe@EXAMPLE", "s3cret")]
        assert user is not None and user.username == "jdoe"

    @override_settings(AD_CLEAN_USERNAME_STRING="EXAMPLE\\")
    def test_a_clean_username_string_is_stripped_before_the_bind(self):
        """A site whose users type DOMAIN\\username at the form."""
        user, directory = self.attempt("EXAMPLE\\jdoe", "s3cret")

        assert directory.connection.binds == [("jdoe@EXAMPLE", "s3cret")]
        assert user is not None and user.username == "jdoe"

    def test_the_search_uses_the_configured_dn_and_attribute(self):
        _, directory = self.attempt("jdoe", "s3cret")
        base, scope, filterstr, attrlist = directory.connection.searches[0]

        assert base == "DC=example,DC=com"
        assert scope == ldap.SCOPE_SUBTREE
        assert filterstr == "sAMAccountName=jdoe"
        assert "memberOf" in attrlist


class TestQualifyingGroups(ADTestCase):
    """Who may sign in at all.

    ``qualified_ad_group_names()`` returning empty means *everybody who
    authenticates*, and one qualifying group means *only members of it*. That
    is an access-control decision taken in ``backends.py`` on the strength of
    rows an administrator ticked, and nothing covered either branch.
    """

    def test_with_no_qualifying_groups_any_authenticated_user_is_admitted(self):
        assert models.ActiveDirectoryGroupMap.qualified_ad_group_names() == []
        user, _ = self.attempt("jdoe", "s3cret")
        assert user is not None

    def test_a_member_of_a_qualifying_group_is_admitted(self):
        models.ActiveDirectoryGroupMap.objects.create(ad_group="Physics", account_qualifier=True)
        user, _ = self.attempt("jdoe", "s3cret")
        assert user is not None

    def test_a_user_in_no_qualifying_group_is_refused_and_left_uncreated(self):
        """Authenticated, and still refused - and no account to show for it.

        The order matters and is not obvious from the outside: the group check
        runs before ``get_or_create_user()``, so a refused user leaves no row.
        If that order were reversed, every AD account in the directory could be
        created in QATrack+ by anyone typing its password.
        """
        models.ActiveDirectoryGroupMap.objects.create(ad_group="Radiation", account_qualifier=True)

        user, directory = self.attempt("jdoe", "s3cret")

        assert user is None
        assert not User.objects.filter(username="jdoe").exists()
        # The bind itself succeeded; this is a refusal after authentication.
        assert directory.connection.binds == [("jdoe@EXAMPLE", "s3cret")]

    def test_a_group_map_row_that_is_not_a_qualifier_does_not_gate_anybody(self):
        """account_qualifier=False maps groups without restricting sign-in."""
        models.ActiveDirectoryGroupMap.objects.create(ad_group="Radiation", account_qualifier=False)

        user, _ = self.attempt("jdoe", "s3cret")
        assert user is not None


class TestGroupMembership(ADTestCase):
    """What a signed-in AD user can do, which is decided by their groups."""

    def setUp(self):
        super().setUp()
        self.physics = Group.objects.create(name="Physics QC")
        self.everyone = Group.objects.create(name="Everyone")

    def test_a_mapped_ad_group_becomes_a_qatrack_group(self):
        mapping = models.ActiveDirectoryGroupMap.objects.create(ad_group="Physics")
        mapping.groups.add(self.physics)

        user, _ = self.attempt("jdoe", "s3cret")

        assert list(user.groups.all()) == [self.physics]

    def test_default_groups_are_applied_to_every_ad_user(self):
        models.DefaultGroup.objects.create(group=self.everyone)

        user, _ = self.attempt("jdoe", "s3cret")

        assert list(user.groups.all()) == [self.everyone]

    def test_an_unmapped_ad_group_adds_nothing(self):
        user, _ = self.attempt("jdoe", "s3cret")
        assert list(user.groups.all()) == []

    def test_a_group_leaves_the_user_when_the_directory_drops_it(self):
        """It does not, and that is worth having written down.

        ``update_user_attributes()`` only ever calls ``groups.add()``. A user
        removed from an AD group keeps the QATrack+ group it mapped to, for as
        long as the account exists - so revoking access in the directory does
        not revoke it here. Asserted as the behaviour it is, not as the
        behaviour it should be; changing it is a decision about existing sites,
        not a bug fix.
        """
        mapping = models.ActiveDirectoryGroupMap.objects.create(ad_group="Physics")
        mapping.groups.add(self.physics)
        user, _ = self.attempt("jdoe", "s3cret")
        assert list(user.groups.all()) == [self.physics]

        self.jdoe.groups = []
        user, _ = self.attempt("jdoe", "s3cret")

        assert list(user.groups.all()) == [self.physics]

    @override_settings(AD_MIRROR_GROUPS=True)
    def test_mirroring_creates_the_ad_group_and_also_its_container(self):
        """Mirroring creates a QATrack+ group per *CN component* of the DN.

        ``get_user_attrs()`` treats every ``CN=`` part of a memberOf value as a
        group name, and a real memberOf is
        ``CN=Physics,CN=Users,DC=example,DC=com`` - so the container comes
        through as a membership too. With AD_MIRROR_GROUPS off it is harmless,
        because ``Group.objects.get()`` raises DoesNotExist and the backend
        passes. With it on, the container is created as a QATrack+ group.

        Asserted so that it is visible rather than surprising. Whether
        mirroring should parse only the leading CN is a question for the people
        who run mirrored sites.
        """
        self.jdoe.groups = ["Physics"]

        user, _ = self.attempt("jdoe", "s3cret")

        names = sorted(g.name for g in user.groups.all())
        assert names == ["Physics", "Users"]


class TestTLSOptions(ADTestCase):
    """The options set on the ``ldap`` module itself, before any connection.

    These are set in ``__init__``, so they are set once per backend instance
    and recorded separately from the per-connection options - see
    ``FakeDirectory.module_options``.
    """

    def test_referrals_are_always_turned_off(self):
        """Carries a "DO NOT TURN THIS OFF OR SEARCH WON'T WORK" comment.

        A comment is not a check. Searching an AD forest follows referrals the
        client cannot chase, and the symptom is an empty result rather than an
        error - which in ``get_user_attrs()`` is an IndexError on ``[0]``,
        reported as "Exception occurred while trying to authenticate".
        """
        _, directory = self.attempt("jdoe", "s3cret")
        assert (ldap.OPT_REFERRALS, 0) in directory.module_options

    def test_no_cert_file_sets_no_tls_option(self):
        _, directory = self.attempt("jdoe", "s3cret")
        options = dict(directory.module_options)
        assert ldap.OPT_X_TLS_CACERTFILE not in options

    @override_settings(AD_CERT_FILE="/etc/ssl/certs/ad-ca.pem")
    def test_a_cert_file_reaches_the_tls_trust_option(self):
        """The LDAPS trust path: AD_CERT_FILE is only ever read here.

        A site using ldaps:// with a private CA depends on this one call, and
        the failure mode when it is missing is a TLS error at bind time that
        says nothing about the setting.
        """
        _, directory = self.attempt("jdoe", "s3cret")
        options = dict(directory.module_options)

        assert options[ldap.OPT_X_TLS_CACERTFILE] == "/etc/ssl/certs/ad-ca.pem"

    def test_the_connection_is_pinned_to_protocol_version_3(self):
        _, directory = self.attempt("jdoe", "s3cret")
        assert (ldap.OPT_PROTOCOL_VERSION, 3) in directory.connection.options


# The two backends a site running AD actually configures: the shipped
# AUTHENTICATION_BACKENDS lists QATrackAccountBackend and has the AD backend
# commented out below it, so switching AD on means having both.
BOTH_BACKENDS = [
    'qatrack.accounts.backends.QATrackAccountBackend',
    'qatrack.accounts.backends.ActiveDirectoryGroupMembershipSSLBackend',
]


@override_settings(AUTHENTICATION_BACKENDS=BOTH_BACKENDS)
class TestTheLocalSideDoor(ADTestCase):
    """A locally created account must keep working once AD is switched on.

    This is the door a site needs when the directory is the thing that is
    broken. A clinic whose AD server is down, or whose network path to it is
    down, still has QC to review and service events to close, and the only way
    back in is an account QATrack+ holds itself - which in practice is the
    superuser made by `createsuperuser` during the install, plus whatever local
    accounts an administrator has added.

    It is not obvious that it works, and it is the kind of thing that breaks
    silently: nothing fails until the day the directory is unreachable, which
    is the worst day to find out. What makes it work is that
    `ActiveDirectoryGroupMembershipSSLBackend.authenticate()` returns None for
    every failure rather than raising - including `SERVER_DOWN` and anything
    its bare `except Exception` catches - so Django moves on to the next
    backend in the list. Each test below therefore checks that the directory
    really was consulted and really did fail, so that a pass cannot come from
    the AD backend having been skipped.

    Asked for by Cody, 2026-11-03, as the "side door" sites rely on.
    """

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('local-admin', 'admin@example.com', 'localpw')
        self.operator = User.objects.create_user('local-op', 'op@example.com', 'localpw')

    def sign_in(self, username, password, users=None, **directory_kwargs):
        """Through django.contrib.auth.authenticate, so the whole chain runs.

        The other classes in this file call one backend directly, which is
        right for testing that backend. It is wrong here: what is under test is
        the fall-through from one backend to the next, which only
        `authenticate()` does.
        """
        directory = FakeDirectory(
            users if users is not None else [self.jdoe],
            settings=django_settings,
            **directory_kwargs,
        )
        with directory.patch():
            user = authenticate(None, username=username, password=password)
        return user, directory

    def test_the_backends_are_both_configured(self):
        """The fixture itself, asserted - every test below depends on it."""
        assert django_settings.AUTHENTICATION_BACKENDS == BOTH_BACKENDS

    def test_a_local_superuser_signs_in_with_ad_configured(self):
        user, _ = self.sign_in('local-admin', 'localpw')

        assert user is not None
        assert user.username == 'local-admin'
        assert user.is_superuser

    def test_a_local_regular_user_signs_in_with_ad_configured(self):
        user, _ = self.sign_in('local-op', 'localpw')

        assert user is not None
        assert user.username == 'local-op'
        assert not user.is_superuser

    def test_a_local_superuser_signs_in_while_the_directory_is_down(self):
        """The scenario this exists for: AD is unreachable and an admin needs in.

        In the shipped order the local backend comes first, so a local account
        is not merely admitted during an outage - the directory is never
        consulted at all. That is the strongest form of the guarantee, and it
        is what the assertion says. The AD-first order, where the backend does
        run and has to fail quietly, is tested below.
        """
        user, directory = self.sign_in('local-admin', 'localpw', server_down=True)

        assert user is not None and user.is_superuser
        assert directory.initialize_calls == [], (
            "the directory was consulted for a local account that had already "
            "authenticated - harmless in itself, but it means this test is no "
            "longer measuring what its docstring claims"
        )

    @override_settings(AUTHENTICATION_BACKENDS=list(reversed(BOTH_BACKENDS)))
    def test_a_local_user_signs_in_when_the_directory_cannot_be_opened_at_all(self):
        """A step earlier than SERVER_DOWN: ldap.initialize() itself raising.

        A bad AD_LDAP_URL, or DNS failure, raises before there is a connection
        object - which also means the backend's `finally` clause calls
        `unbind_s()` on a name that was never assigned. That NameError is
        swallowed by the bare `except Exception` around it, and this is the
        test that says so: a change to that `finally` could otherwise turn an
        AD outage into a total lockout.

        Needs the directory listed first. With the local backend first the AD
        backend is never reached, and the test would pass without the failure
        path ever running.
        """
        user, directory = self.sign_in(
            'local-admin', 'localpw', initialize_raises=OSError('no route to host'))

        assert user is not None and user.is_superuser
        # initialize() raised, so there is no connection to inspect. That it
        # was *called* is what distinguishes this from a backend that was never
        # reached, which is the only way this test means anything.
        assert directory.initialize_calls == ['ldap://ad.example.com:389']
        assert directory.connections == []

    def test_a_local_password_is_tried_before_the_directory(self):
        """A name that exists in both places: the local account answers first.

        Only true for this backend order, which is the shipped one. The test
        below covers the other order.
        """
        both = FakeUser('local-admin', 'the-ad-password')

        user, directory = self.sign_in('local-admin', 'localpw', users=[both])

        assert user is not None and user.is_superuser
        assert directory.connections == [], "the directory was consulted unnecessarily"

    @override_settings(AUTHENTICATION_BACKENDS=list(reversed(BOTH_BACKENDS)))
    def test_the_side_door_works_with_the_directory_listed_first(self):
        """Some sites put AD first. The local account must still get in.

        With AD first the directory is asked about every sign-in, so a local
        account only works because the AD backend returns None instead of
        raising. That makes this the stricter of the two orders, and the one
        where an unhandled exception would lock everybody out.
        """
        user, directory = self.sign_in('local-admin', 'localpw', server_down=True)

        assert user is not None and user.is_superuser
        assert directory.connection.binds, "the directory was never contacted"

    def test_an_ad_account_cannot_use_the_side_door(self):
        """The control, and the reason the side door is not a hole.

        An account the directory created has no usable password - the backend
        calls set_unusable_password() precisely so that it cannot be signed
        into locally. So when the directory is down, AD users are out, which is
        correct: their credentials live in the directory. If this ever passed,
        it would mean an AD account could be signed into with something other
        than the directory's password.
        """
        user, _ = self.sign_in('jdoe', 's3cret')
        assert user is not None, "the AD user could not sign in while AD was up"
        assert not User.objects.get(username='jdoe').has_usable_password()

        during_outage, directory = self.sign_in('jdoe', 's3cret', server_down=True)

        assert during_outage is None
        assert directory.connection.binds, "the directory was never contacted"

    def test_the_side_door_still_refuses_a_wrong_local_password(self):
        """It is a door, not an absence of one."""
        user, _ = self.sign_in('local-admin', 'not-the-password', server_down=True)
        assert user is None

    def test_an_unknown_name_is_refused_during_an_outage(self):
        user, _ = self.sign_in('nobody-at-all', 'whatever', server_down=True)
        assert user is None
