"""A stand-in directory, so the Active Directory sign-in path can be driven.

``ActiveDirectoryGroupMembershipSSLBackend`` has never been exercised beyond
``clean_username()``. What has never run at all is the whole path: bind, user
lookup, the qualifying-group check, and the QATrack+ account and groups that
come out the other end. That path decides whether somebody can sign in and
what they can see once they have, and it is configured by eleven ``AD_*``
settings that nothing checks.

**Why a fake and not a server.** A dockerised directory is a separate piece of
work, and the two are complements rather than alternatives: a fake proves our
code's logic, a real server proves our assumptions about a directory. The fake
runs anywhere, in the test's own process, with no service to start - which is
also what lets it work under the Selenium harness, where the live server runs
in a thread of that same process and a patch applied from the test method
reaches the backend.

**python-ldap has to be installed; only its calls are replaced.** Mocking the
connection is not enough, because ``backends.py`` reads ``ldap.SCOPE_SUBTREE``,
``ldap.OPT_REFERRALS``, ``ldap.OPT_X_TLS_CACERTFILE``,
``ldap.INVALID_CREDENTIALS`` and ``ldap.SERVER_DOWN`` from the module - so the
module must exist, with its real constants and its real exception classes. The
alternative, injecting a fake ``ldap`` into ``sys.modules``, would have meant
this file encoding assumptions about python-ldap's API that nothing verifies,
which is the one failure a fake directory is prone to. Tests using this are
therefore guarded by ``pytest.importorskip("ldap")``; see
``docs/developer/guide.rst`` for installing the extra.

**What this does not prove.** That our LDAP calls are the right calls. The fake
answers ``simple_bind_s`` and ``search_ext_s`` the way we believe a directory
answers them; if that belief is wrong, these tests pass and a real sign-in
still fails. Only a real directory can close that gap.
"""

from unittest import mock

try:
    import ldap
except ImportError:  # pragma: no cover - mirrors backends.py's own guard
    # Guarded so that importing this module never fails, which lets the test
    # modules that use it put `pytest.importorskip("ldap")` at their top and be
    # skipped rather than collected as errors. Every attribute below is reached
    # only from a test that has passed that guard.
    ldap = None

# The directory shape AD hands back: attribute values arrive as lists of
# bytes, which is why backends.py decodes them. Keeping bytes here means the
# decode path runs rather than being skipped by a friendlier fake.
DEFAULT_DOMAIN_DN = "DC=example,DC=com"


def member_of(*group_names, container="Users", domain_dn=DEFAULT_DOMAIN_DN):
    """Build ``memberOf`` values in the format a directory returns.

    One distinguished name per group, e.g.::

        CN=Physics,CN=Users,DC=example,DC=com

    Worth knowing while reading the tests: ``get_user_attrs()`` takes *every*
    ``CN=`` component of each DN as a group name, so the ``container`` above
    ends up in the user's memberships alongside the real groups. That is the
    backend's behaviour, not an artefact of this helper, and the tests say so
    where it matters.
    """
    return [
        ("CN=%s,CN=%s,%s" % (name, container, domain_dn)).encode()
        for name in group_names
    ]


class FakeUser:
    """One account in the stand-in directory."""

    def __init__(self, username, password, *, email="", surname="", given_name="", groups=()):
        self.username = username
        self.password = password
        self.email = email
        self.surname = surname
        self.given_name = given_name
        self.groups = list(groups)

    def attributes(self, settings):
        """The attribute dictionary a search returns, keyed by the AD_LU_* names.

        Keyed from the settings rather than from literals: a site can point
        AD_LU_MAIL at a different attribute, and a fake that hardcoded "mail"
        would quietly stop answering the lookup the backend actually makes.
        """
        return {
            settings.AD_LU_MAIL: [self.email.encode()],
            settings.AD_LU_SURNAME: [self.surname.encode()],
            settings.AD_LU_GIVEN_NAME: [self.given_name.encode()],
            settings.AD_LU_ACCOUNT_NAME: [self.username.encode()],
            settings.AD_LU_MEMBER_OF: member_of(*self.groups) if self.groups else [b""],
        }


class FakeConnection:
    """What ``ldap.initialize()`` returns: one bind's worth of a directory.

    Everything it is asked is recorded, because several of the things worth
    asserting are arguments rather than outcomes - the bind DN carries the
    result of username cleaning and AD_NT4_DOMAIN, and the search carries
    AD_SEARCH_DN and AD_LU_ACCOUNT_NAME.
    """

    def __init__(self, directory, url):
        self.directory = directory
        self.url = url
        self.options = []
        self.binds = []
        self.searches = []
        self.unbound = False

    def set_option(self, option, value):
        self.options.append((option, value))

    def simple_bind_s(self, who, cred):
        self.binds.append((who, cred))
        if self.directory.server_down:
            raise ldap.SERVER_DOWN("the fake directory is configured as unreachable")
        # The bind DN is "<username>@<AD_NT4_DOMAIN>"; the directory is keyed
        # by username, so split the domain back off rather than requiring every
        # test to spell the domain into its user fixture.
        username = who.split("@")[0]
        user = self.directory.users.get(username)
        if user is None or user.password != cred:
            raise ldap.INVALID_CREDENTIALS(
                {"desc": "Invalid credentials", "info": "fake directory: no such user, or wrong password"}
            )
        self.bound_as = user
        return (97, [], 1, [])  # python-ldap's result tuple for a successful bind

    def search_ext_s(self, base, scope, filterstr, attrlist=None, *args, **kwargs):
        self.searches.append((base, scope, filterstr, attrlist))
        # The backend filters on "<AD_LU_ACCOUNT_NAME>=<username>", and then
        # takes result[0][1] - so a search that matched nothing would raise
        # IndexError inside the backend rather than returning None. Serving
        # only the user who just bound keeps that path out of these tests;
        # a test that wants it asks for it explicitly.
        user = getattr(self, "bound_as", None)
        if user is None:
            return []
        return [("CN=%s,%s" % (user.username, DEFAULT_DOMAIN_DN), user.attributes(self.directory.settings))]

    def unbind_s(self):
        self.unbound = True


class FakeDirectory:
    """The patch, and the record of what the backend did to it."""

    def __init__(self, users, settings, *, server_down=False, initialize_raises=None):
        self.users = {u.username: u for u in users}
        self.settings = settings
        self.server_down = server_down
        self.initialize_raises = initialize_raises
        self.connections = []
        # Every initialize() call, recorded before it may raise. Without this
        # there is no way to tell "the directory was asked and could not be
        # opened" from "the backend was never reached", and a fall-through test
        # cannot prove it is testing a fall-through.
        self.initialize_calls = []
        # ldap.set_option is called on the *module*, before any connection
        # exists - it is how AD_CERT_FILE reaches OPT_X_TLS_CACERTFILE - so it
        # is recorded separately from the per-connection options.
        self.module_options = []

    def initialize(self, url, *args, **kwargs):
        self.initialize_calls.append(url)
        if self.initialize_raises is not None:
            raise self.initialize_raises
        connection = FakeConnection(self, url)
        self.connections.append(connection)
        return connection

    def set_option(self, option, value):
        self.module_options.append((option, value))

    @property
    def connection(self):
        """The one connection, asserting that there was exactly one."""
        assert len(self.connections) == 1, "expected one connection, got %d" % len(self.connections)
        return self.connections[0]

    def patch(self):
        """Replace ``ldap.initialize`` and ``ldap.set_option`` for the duration.

        A context manager, so a test can enter it around the whole of a
        browser interaction. Patching module attributes is process-wide, which
        is what makes it reach the live-server thread as well as the test's.
        """
        return mock.patch.multiple("ldap", initialize=self.initialize, set_option=self.set_option)
