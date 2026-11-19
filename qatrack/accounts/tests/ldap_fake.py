"""A stand-in directory, so the Active Directory sign-in path can be driven.

It runs in the test's own process, so it also works under the Selenium harness,
whose live server is a thread of that process.

**python-ldap has to be installed; only its calls are replaced**, because
``backends.py`` reads real constants and exception classes from the module. The
dev group provides it; see ``docs/developer/guide.rst`` for the system packages
it needs on Linux.

**What this does not prove**: that our LDAP calls are the right calls. It
answers ``simple_bind_s``, ``bind_s`` and ``search_ext_s`` the way we believe a
directory does; only a real directory can check that belief.
"""

from unittest import mock

# Imported plainly, not guarded. python-ldap is in the `dev` dependency group
# alongside pytest, so a missing module here means a broken environment and
# should say so rather than letting the tests that depend on it disappear.
import ldap

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

        A profile value of ``None`` leaves the attribute out altogether, which is
        what a real directory does for a user with no mailbox or no surname.
        """
        profile = {
            settings.AD_LU_MAIL: self.email,
            settings.AD_LU_SURNAME: self.surname,
            settings.AD_LU_GIVEN_NAME: self.given_name,
            settings.AD_LU_ACCOUNT_NAME: self.username,
        }
        attrs = {name: [value.encode()] for name, value in profile.items() if value is not None}
        attrs[settings.AD_LU_MEMBER_OF] = member_of(*self.groups) if self.groups else [b""]
        return attrs


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

    def bind_s(self, who, cred, method=None):
        """The generic bind, as ``WindowsIntegratedAuthenticationBackend`` uses.

        That backend does not authenticate anybody with it: the web server has
        already done that, and this bind is a *service account* opening a
        connection so the backend can look the user up. It is recorded on the
        same ``binds`` list as ``simple_bind_s`` - what a test cares about is
        which identity was presented, not which of the two calls carried it.

        Without this method the backend could not be driven at all: the call
        raised ``AttributeError``, which ``configure_user``'s bare
        ``except Exception`` turned into a silent "no user".
        """
        return self.simple_bind_s(who, cred)

    def search_ext_s(self, base, scope, filterstr, attrlist=None, *args, **kwargs):
        self.searches.append((base, scope, filterstr, attrlist))
        # The backend filters on "<AD_LU_ACCOUNT_NAME>=<username>", and then
        # takes result[0][1] - so a search that matched nothing would raise
        # IndexError inside the backend rather than returning None.
        #
        # Resolved from the *filter*, not from whoever bound. For the sign-in
        # backend those are the same person, which is why serving `bound_as`
        # went unnoticed for so long. WindowsIntegratedAuthenticationBackend
        # binds as a service account and searches for somebody else, so a fake
        # that ignored the filter handed it the service account's own (empty)
        # profile - the first test written for that backend failed on the fake
        # rather than on the code.
        #
        # An unbound connection still returns nothing, which is the honest
        # answer; the backend's IndexError-on-empty-result path remains
        # uncovered, because it only searches after a successful bind.
        if getattr(self, "bound_as", None) is None:
            return []
        wanted = filterstr.split("=", 1)[1] if "=" in filterstr else None
        user = self.directory.users.get(wanted)
        if user is None:
            return []
        attrs = user.attributes(self.directory.settings)
        if attrlist is not None:
            # A real directory returns only the attributes that were asked for.
            # Returning all of them regardless made the profile assertions below
            # pass even if the backend stopped requesting a field - the test
            # would still see `mail` in the result and conclude the lookup
            # worked. Honouring attrlist is what makes those assertions able to
            # fail. `attrlist=None` means "everything", which is LDAP's own
            # meaning and is left alone.
            attrs = {name: value for name, value in attrs.items() if name in attrlist}
        return [("CN=%s,%s" % (user.username, DEFAULT_DOMAIN_DN), attrs)]

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
