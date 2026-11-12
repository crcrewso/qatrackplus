.. _auth_backends:

Authentication Backends
=======================

QATrack+ can authenticate users against its own database, against an
on-premises Active Directory over LDAP, or against an identity provider that
speaks OAuth2/OpenID Connect - which includes both on-premises AD FS and
Microsoft 365 / Entra ID.

**Which of these you can use depends on what your organization actually runs,
and the difference between on-premises Active Directory and Microsoft 365 is
the one that catches people out.** See :ref:`auth_onprem_vs_cloud` below.

.. list-table::
    :header-rows: 1
    :widths: 24 20 56

    * - Backend
      - Protocol
      - Use it when
    * - ``QATrackAccountBackend``
      - none
      - QATrack+ manages its own users. No extra configuration, no extra
        packages; you create users and group memberships by hand.
    * - :ref:`ActiveDirectoryGroupMembershipSSLBackend <active_directory>`
      - LDAP / LDAPS
      - You have a **domain controller on your network** that QATrack+ can
        reach. Users sign in on QATrack+'s own login form. Needs
        ``python-ldap``.
    * - :ref:`WindowsIntegratedAuthenticationBackend <auth_wia>`
      - LDAP / LDAPS
      - Your web server authenticates the user (IIS Windows Integrated
        Authentication) and QATrack+ only needs to *look up* their name and
        email in the directory. Needs ``python-ldap``.
    * - :ref:`QATrackAdfsAuthCodeBackend <auth_adfs>`
      - OAuth2 / OIDC
      - You run **AD FS**, or you use **Microsoft 365 / Entra ID**. Users are
        redirected to the identity provider to sign in. Needs no extra
        packages - the library ships with QATrack+.

More than one may be listed in ``AUTHENTICATION_BACKENDS``. Django tries each
in turn until one accepts the credentials, so keeping ``QATrackAccountBackend``
in the list is what keeps a way in when the directory is unavailable - see
:ref:`auth_local_door`.

.. _auth_testing_limits:

.. warning::

    **How much of this we can test is limited, and you should assume your
    deployment is one we have never seen.**

    QATrack+'s automated tests cover the LDAP backends against an in-process
    stand-in directory: bind handling, group membership, username cleaning and
    TLS options. Sign-in has also been measured against a Samba domain
    controller. Neither covers referrals, nested groups, multi-domain forests,
    unusual schema or your own topology, and the project has no permanent
    Active Directory, AD FS or Entra tenant to test against.

    The ADFS/Entra backend is tested only at the claim-handling layer; no test
    completes a real OAuth2 redirect against a real identity provider.

    **So please get in touch rather than struggle alone** - open an issue at
    https://github.com/qatrackplus/qatrackplus/issues or ask at
    https://groups.google.com/g/qatrack. A configuration that does *not* work
    is exactly the evidence we cannot generate ourselves.

.. _auth_onprem_vs_cloud:

On-premises Active Directory, or Microsoft 365?
-----------------------------------------------

These are two different things, and only one of them speaks LDAP.

**On-premises Active Directory** means a domain controller running on your
network - the thing that has been there since your domain was created, that
your Windows machines join. It answers LDAP on port 389 and LDAPS on 636, so
QATrack+'s LDAP backends can bind to it directly. If you also run AD FS, the
OAuth2 backend is available as well.

**Microsoft 365 / Entra ID** (formerly Azure AD) is Microsoft's cloud
directory. **It does not answer LDAP binds.** There is no host for
``AD_LDAP_URL`` to point at, so if your organization is cloud-only -
no domain controller of its own - the LDAP backends in this page
**cannot be used at all**, however they are configured. Use
:ref:`QATrackAdfsAuthCodeBackend <auth_adfs_entra>` instead, which talks
OAuth2/OIDC to Entra ID and needs no extra packages.

**Hybrid** - a domain controller on your network *and* Entra ID - is common in
hospitals, and it shifts over time: the LDAP settings that worked on Monday can
stop working after a migration step nobody told you about.

.. important::

    **Several sites are migrating to Microsoft 365 enterprise authentication,
    at various stages.** The :ref:`AD FS / Entra backend <auth_adfs>` is the
    direction of travel; plan on moving QATrack+ to it as part of such a
    migration rather than waiting for LDAP to fail.

What tends to break during one:

* **MFA and conditional access** cannot be satisfied by an LDAP bind - it either
  stops working or bypasses the policy. The OAuth2 route goes through the
  identity provider, so its policies apply.
* **Cloud-only accounts** may have no on-premises object, so new staff cannot
  sign in while existing staff still can.
* **Authentication may move before the directory does**: searches succeed,
  binds fail, and a correct password is rejected.
* **Group membership can diverge**: ``memberOf`` on the local object lags, and
  :ref:`group mapping <ad_group_map>` stops granting what it used to.

If you are at any stage of such a migration, please tell us which (see
:ref:`what we can test <auth_testing_limits>`); these are the setups we see
least of.

.. note::

    Microsoft also sells **Entra Domain Services**, a managed domain that
    *does* offer LDAP and LDAPS. If your organization has it, the LDAP
    backends apply to that rather than to Entra ID itself. Nobody has reported
    using QATrack+ with it, so if you do, please tell us how it went.

If you are not sure which you have, the question to ask whoever administers
your accounts is: *"is there a domain controller I can reach on port 389 or
636, or are we cloud-only?"*

.. _active_directory:

Active Directory
----------------

Using an existing Active Directory server to do your user authentication is a
great way to simply the management of users for your QATrack+ system.  It's
especially convenient for your users that they don't have to remember "yet
another password" and can simply use their network logon.  QATrack+ comes with
an Active Directory backend and it's configuration will be described below.

Installation of python-ldap
...........................

The two LDAP backends need ``python-ldap``, which QATrack+ declares as the
``ldap`` extra. **Install it with the rest of your dependencies rather than by
hand.**

``uv sync`` is exact: it installs the extras the command names and
**uninstalls everything else**, so a package installed by hand is removed by
the next sync, upgrades included.

Below, ``--extra ldap`` is **added to** the sync command your own install or
upgrade page gives you; keep every other flag it has, ``--no-dev`` included.

.. note::

    **Under Docker there is nothing to do.**
    ``deploy/docker/django/Dockerfile`` already installs the ``ldap`` extra, so
    the image carries ``python-ldap`` whether or not you use it. Skip to :ref:`Configuring QATrack+ to use your Active
    Directory Server <active_directory_settings>`, and for LDAPS with your own
    certificate authority see :ref:`docker_ldaps`.

Linux
~~~~~

``python-ldap`` publishes no wheels on PyPI - only a source distribution - so
on Linux it is **compiled during the sync**. Its build dependencies have to be
installed first, or the sync fails partway through with a compiler error:

.. code-block:: console

    sudo apt-get install build-essential python3-dev libldap2-dev libsasl2-dev

``build-essential`` and ``python3-dev`` are already part of the
:ref:`Linux installation <linux_install_40>`; the two ``lib*-dev`` packages are
not, and are the ones usually missing.

Then add the extra to your own sync command. For a PostgreSQL site following
the Linux install guide, that is:

.. code-block:: console

    cd ~/web/qatrackplus
    uv sync --extra postgres --extra ldap --no-dev

``slapd`` and ``ldap-utils`` are sometimes suggested alongside these. They are
an LDAP **server** and its client tools - useful if you want a local directory
to test against, and not needed to authenticate against your organization's.

See https://www.python-ldap.org/en/latest/installing.html for more detail on
building the package.

Windows
~~~~~~~

No system packages are needed. Because there is no wheel on PyPI,
``pyproject.toml`` pins a prebuilt one -
``python_ldap-3.4.5-cp312-cp312-win_amd64.whl``, from
https://github.com/cgohlke/python-ldap-build - and ``uv sync`` fetches that
instead of compiling. The pin applies to ``win32`` on Python 3.12, which is the
only version QATrack+ supports.

Add the extra to the sync command in the :ref:`Windows Server installation
<win_install_40>`:

.. code-block:: console

   >>  uv sync --exact --extra win --extra mssql --extra ldap

The ``mssql`` extra carries ``python-ldap`` as well, so a Windows site that
followed the install guide already has it; naming ``ldap`` says why it is there.

.. note::

    The ``ldap`` extra is not new in 4.1 - it was added in **4.0.2**, and it
    carries ``python-ldap``. If you are on 4.0.2 and already synced with
    ``--extra ldap``, nothing on this page changes for you.

.. note::

    ``uv`` is the only installer that reads the wheel pin. It lives in
    ``[tool.uv.sources]`` in ``pyproject.toml``, which ``pip`` ignores - so if
    you are using the ``pip`` fallback path described in the Windows install
    guide, install the wheel yourself first.

To confirm the installation is working, activate your virtual env and verify the
import works:

.. code-block:: console

    cd C:\deploy\qatrackplus
    .\.venv\Scripts\Activate.ps1
    python -c "import ldap; print(ldap.__version__)"

If that command prints the ldap version then ldap is installed correctly.

.. _auth_check_package:

Checking it before you restart
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Confirm the package after any change to the virtual environment, before
restarting QATrack+.** Nothing warns you if it is missing:

.. code-block:: console

    python -c "import ldap; print(ldap.__version__)"

If that raises ``ModuleNotFoundError``, install it before restarting. Without
it the site starts, but **every sign-in returns a server error** - local
accounts too, in any backend order - because Django builds every backend in
``AUTHENTICATION_BACKENDS`` before any of them authenticates, and building the
Active Directory one needs the missing module. The local account in
:ref:`auth_local_door` covers a directory outage, not this.

.. _active_directory_settings:

Configuring QATrack+ to use your Active Directory Server
........................................................

Copy the following lines to your `local_settings.py` file:

.. code-block:: python

    #-----------------------------------------------------------------------------
    # Authentication backend settings
    AUTHENTICATION_BACKENDS = (
        'qatrack.accounts.backends.QATrackAccountBackend',
        'qatrack.accounts.backends.ActiveDirectoryGroupMembershipSSLBackend',
    )

    # active directory settings (not required if only using ModelBackend
    AD_DNS_NAME = 'your.ad.server.yourhospital.com'

    # LDAPS, which is what most directories now require - see
    # "Encrypting the connection to the directory" below.
    AD_LDAP_PORT = 636
    AD_LDAP_URL = 'ldaps://%s:%s' % (AD_DNS_NAME, AD_LDAP_PORT)

    # Unencrypted, only against a directory you know permits it:
    # AD_LDAP_PORT = 389
    # AD_LDAP_URL = 'ldap://%s:%s' % (AD_DNS_NAME, AD_LDAP_PORT)

    AD_CERT_FILE = None  # AD_CERT_FILE='/path/to/your/cert.txt'

    AD_SEARCH_DN = "dc=yourdomain,dc=yourhospital,dc=com"
    AD_NT4_DOMAIN = "YOURDOMAIN"  # Network domain that AD server is part of

    AD_SEARCH_FIELDS = ['mail', 'givenName', 'sn', 'sAMAccountName', 'memberOf']

    AD_DEBUG_FILE = "C:/deploy/qatrackplus/logs/ad_log.txt"
    AD_DEBUG = False # set to True and restart QATrack+ Web Service if you need to debug AD Connection

You will also have to set ``AD_DNS_NAME``, ``AD_SEARCH_DN`` and
``AD_NT4_DOMAIN`` to suit your own Active Directory.  The complete set of
Active Directory settings are described here: :ref:`Active Directory Settings
<settings_ad>`.

With SSL (``ldaps``), set ``AD_CERT_FILE`` when your directory server's
certificate comes from your organization's own certificate authority (CA): the
path to that CA's certificate, in PEM format, in a file the user QATrack+ runs
as can read. See ``AD_CERT_FILE`` in :ref:`Active Directory Settings
<settings_ad>`, and if you run QATrack+ with Docker, :ref:`docker_ldaps`.

After you have saved that file, you will need to restart your application
server (or for example your CherryPy service).

.. _auth_ldap_tls:

Encrypting the connection to the directory
..........................................

**An LDAP bind sends the user's password to the directory.** Over an
unencrypted connection it goes in clear text, so use **LDAPS**: set
``AD_LDAP_URL`` to ``ldaps://<your directory>:636``.

``AD_CERT_FILE`` is the certificate authority that signed the directory's
certificate. Leave it unset for a public CA, and set it to your own CA's
certificate in PEM format when your organization signs its own - see
``AD_CERT_FILE`` in :ref:`Active Directory Settings <settings_ad>`, and
:ref:`docker_ldaps` if you run QATrack+ with Docker.

.. note::

    **A current domain controller may refuse an unencrypted bind.** Microsoft
    has recommended LDAP signing since 2020, and a new Windows Server 2025
    domain enforces it out of the box. When it does, the user sees only the
    ordinary bad-password error, and QATrack+ logs *"Exception occurred while
    trying to authenticate"* with ``STRONG_AUTH_REQUIRED`` (*"Transport
    encryption required"*) in the traceback. If sign-in is failing and you are
    on ``ldap://`` port 389, this is the first thing to change.

    **Measured** against a Samba Active Directory domain controller, which
    refuses an unencrypted simple bind by default.

.. note::

    **What has been tested, and what has not.** LDAPS has been exercised
    against a real directory: a certificate signed by the expected CA signs the
    user in, one signed by a different CA is refused, and an unset
    ``AD_CERT_FILE`` against a privately signed server is refused. That is the
    transport to use.

    Encryption negotiated on port 389 instead - StartTLS - is **not supported**;
    QATrack+ only speaks LDAPS. If your network allows nothing but 389, tell us,
    because that is the case which would justify adding it:
    https://github.com/qatrackplus/qatrackplus/issues

.. _auth_wia:

Windows Integrated Authentication
---------------------------------

``qatrack.accounts.backends.WindowsIntegratedAuthenticationBackend`` is for a
deployment where **the web server has already authenticated the user** - IIS
with Windows Integrated Authentication, for example - and passes the username
to QATrack+. The backend trusts that username and does not verify a password.

.. warning::

    **Django's own** ``RemoteUserMiddleware`` **does not reach this backend.**
    The middleware, which ``settings.py`` ships commented out for this purpose,
    passes the web server's username as ``remote_user``; this backend accepts
    ``username``, so Django skips it and the request stays signed out. Measured
    on Django 4.2: no account is created and the browser is sent to the login
    page, while Django's own ``RemoteUserBackend`` signs the same request in.
    See `Authentication using REMOTE_USER
    <https://docs.djangoproject.com/en/4.2/howto/auth-remote-user/>`__. If you
    run this backend today, please tell us how:
    https://github.com/qatrackplus/qatrackplus/issues

It still uses LDAP, but not to authenticate. When it creates a user for the
first time it binds to the directory with a **service account**
(``AD_LDAP_USER`` and ``AD_LDAP_PW``, which are used by nothing else), looks up
the username the web server supplied, and copies ``mail``, ``givenName`` and
``sn`` onto the new QATrack+ user. If that lookup fails - no ``python-ldap``, a
wrong ``AD_LDAP_PW``, no match - the **first** sign-in is refused, but the user
row is already created, so the next one signs in with no name or email and the
lookup is not retried. Pinned by ``TestWindowsIntegratedAuthentication``.

**There is no AD FS or Entra equivalent of this.** Claims only ever arrive for
the person who completed the sign-in redirect, so an identity provider cannot
tell QATrack+ about a user that the web server authenticated. If you
authenticate at the web server and want real names and email addresses, LDAP
is the only route.

.. _auth_local_door:

Keeping a way in when the directory is unavailable
--------------------------------------------------

**Keep** ``QATrackAccountBackend`` **in** ``AUTHENTICATION_BACKENDS`` **and
keep at least one local account with a known password you have written down
somewhere other than QATrack+.**

Django `tries each backend in turn
<https://docs.djangoproject.com/en/4.2/topics/auth/customizing/#specifying-authentication-backends>`__
until one returns a user, so a local account
signs in from QATrack+'s own login form even while the directory is
unreachable. This matters on a clinical system: if your only route in depends
on a directory, an outage locks everybody out, administrators included.

The **order** does not decide whether that works - every backend gets a turn
either way. What it decides is:

* **which wins for a username that exists in both.** The first backend to
  accept the credentials is the one used.
* **how long a local sign-in takes during an outage.** With an LDAP backend
  listed first, each attempt waits for the connection to the directory to time
  out before QATrack+ tries the local password, so the login form can appear to
  hang for as long as that timeout. Listing ``QATrackAccountBackend`` first
  avoids the wait, which is the only reason to prefer that order.

.. code-block:: python

    AUTHENTICATION_BACKENDS = [
        'qatrack.accounts.backends.QATrackAccountBackend',
        'qatrack.accounts.backends.ActiveDirectoryGroupMembershipSSLBackend',
    ]

This works because the credentials are posted to QATrack+. **Under AD FS or
Entra ID they are not** - the user is redirected away to sign in, so if the
identity provider is unreachable that flow has no fallback. A local account
still works through the ordinary login form, which is one more reason to keep
one.

.. warning::

    **This covers an outage, not a missing** ``python-ldap``: then every
    sign-in fails before the local account gets its turn. See
    :ref:`auth_check_package`.

.. _auth_adfs:

Active Directory Federation Services (ADFS)
-------------------------------------------

As of version 3.1.0 comes with an ADFS backend for Single Sign On (SSO).  This
can provide a convenient way for your users to log into QATrack+ using their
hospital network login.

Use ``qatrack.accounts.backends.QATrackAdfsAuthCodeBackend``, a wrapper around
the library's `AdfsAuthCodeBackend
<https://github.com/snok/django-auth-adfs/blob/1.16.0/django_auth_adfs/backend.py>`__
that adds QATrack+'s username cleaning and group mapping:

.. code:: python

    AUTHENTICATION_BACKENDS = [
        'qatrack.accounts.backends.QATrackAccountBackend',
        'qatrack.accounts.backends.QATrackAdfsAuthCodeBackend',
    ]

The library's own ``django_auth_adfs.backend.AdfsAuthCodeBackend`` does not work
in its place: QATrack+ mounts its AD FS sign-in URLs only when it finds the
wrapper in ``AUTHENTICATION_BACKENDS``.


Upstream documentation
......................

The backend wraps `django-auth-adfs
<https://django-auth-adfs.readthedocs.io/en/stable/>`__, and QATrack+ passes
``AUTH_ADFS`` to it almost unchanged, so its documentation is the reference for
anything this page does not cover. QATrack+ installs 1.16.0 (`source
<https://github.com/snok/django-auth-adfs/tree/1.16.0>`__); the links below go
to the library's stable documentation.

* `Settings reference
  <https://django-auth-adfs.readthedocs.io/en/stable/settings_ref.html>`__ -
  every key ``AUTH_ADFS`` accepts, including `SERVER
  <https://django-auth-adfs.readthedocs.io/en/stable/settings_ref.html#server>`__,
  `TENANT_ID
  <https://django-auth-adfs.readthedocs.io/en/stable/settings_ref.html#tenant-id>`__,
  `CLIENT_ID
  <https://django-auth-adfs.readthedocs.io/en/stable/settings_ref.html#client-id>`__
  and `AUDIENCE
  <https://django-auth-adfs.readthedocs.io/en/stable/settings_ref.html#audience>`__.
* `Microsoft 365 / Entra ID (Azure AD) configuration guide
  <https://django-auth-adfs.readthedocs.io/en/stable/azure_ad_config_guide.html>`__ -
  registering the application and what to put in ``settings.py``. This is the
  one to follow for a cloud tenant.
* On-premises AD FS guides, by server version: `AD FS 4.0
  <https://django-auth-adfs.readthedocs.io/en/stable/adfs_4.0_config_guide.html>`__
  and `AD FS 3.0
  <https://django-auth-adfs.readthedocs.io/en/stable/adfs_3.0_config_guide.html>`__.
* `How the OAuth2 flow works
  <https://django-auth-adfs.readthedocs.io/en/stable/oauth2_explained.html>`__ -
  worth reading once if the redirect behaviour is unfamiliar.
* `Troubleshooting
  <https://django-auth-adfs.readthedocs.io/en/stable/troubleshooting.html>`__
  and the `FAQ
  <https://django-auth-adfs.readthedocs.io/en/stable/faq.html>`__ - start here
  when a sign-in fails, since most failures are in the identity provider's
  configuration rather than in QATrack+.

Configuring your ADFS Server
............................

The guides below cover the QATrack+ side. For the identity provider itself,
the upstream guides linked above are more current.

Please see the following guides to configure your ADFS Server to allow
access for QATrack+:

.. toctree::
    :maxdepth: 1

    adfs_server_2016
    adfs_server_2012


.. _auth_adfs_settings:

Configuring QATrack+ to use ADFS
................................

Copy the following lines to your `local_settings.py` file:

.. code:: python

    AUTHENTICATION_BACKENDS = [
        'qatrack.accounts.backends.QATrackAccountBackend',
        'qatrack.accounts.backends.QATrackAdfsAuthCodeBackend',
    ]

    # AD FS settings.
    AUTH_ADFS = {
        "SERVER": "some.adfs.server.com",
        "CLIENT_ID": "qatrackplus",
        "RELYING_PARTY_ID": "https://your.qatrackserver.com",
        "AUDIENCE": "https://your.qatrackserver.com",
        "CLAIM_MAPPING": {
            "first_name": "given_name",
            "last_name": "family_name",
            "email": "email"
        },
        "USERNAME_CLAIM": "winaccountname",
        "GROUPS_CLAIM": "group",
    }


That form is for an **on-premises AD FS server**: ``SERVER`` is its hostname,
and the two guides above describe setting it up on Windows Server.

If you require a different configuration for some reason, more options and settings
are described in https://django-auth-adfs.readthedocs.io/en/stable/settings_ref.html

.. _auth_adfs_entra:

Microsoft 365 / Entra ID instead of an AD FS server
...................................................

The same backend works against **Microsoft 365 / Entra ID** (formerly Azure
AD), with no AD FS server and no extra Python packages. This is the route for
an organization that is cloud-only, because :ref:`Entra ID does not answer LDAP
binds <auth_onprem_vs_cloud>` and the LDAP backends cannot be used at all.

Set ``TENANT_ID`` **instead of** ``SERVER`` - the underlying library switches to
Entra ID mode when it sees a tenant, and points itself at
``login.microsoftonline.com``. Setting both is rejected at start-up:

.. code:: python

    AUTHENTICATION_BACKENDS = [
        'qatrack.accounts.backends.QATrackAccountBackend',
        'qatrack.accounts.backends.QATrackAdfsAuthCodeBackend',
    ]

    AUTH_ADFS = {
        # Your Entra tenant's directory (tenant) ID, from the Azure portal.
        # Do NOT also set "SERVER" - the two are mutually exclusive.
        "TENANT_ID": "00000000-0000-0000-0000-000000000000",
        "CLIENT_ID": "<the application (client) ID of your app registration>",
        # A secret created on the app registration; keep it out of version control.
        "CLIENT_SECRET": "<client secret>",
        "RELYING_PARTY_ID": "<the application (client) ID>",
        "AUDIENCE": "<the application (client) ID>",
        "CLAIM_MAPPING": {
            "first_name": "given_name",
            "last_name": "family_name",
            "email": "upn",
        },
        "USERNAME_CLAIM": "upn",
        "GROUPS_CLAIM": "groups",
    }

On the Entra side, whoever administers your tenant registers QATrack+ as an
application, creates a client secret, adds a **web** redirect URI of
``https://your.qatrackserver.com/accounts/oauth2/callback``, and configures the
app to emit a groups claim. The claim names differ from on-premises AD FS -
``upn`` and ``groups`` rather than ``winaccountname`` and ``group`` - so the
``USERNAME_CLAIM`` and ``GROUPS_CLAIM`` above are not interchangeable with the
AD FS form.

**Follow upstream's guide for the tenant side:** `Azure AD / Entra ID
configuration guide
<https://django-auth-adfs.readthedocs.io/en/stable/azure_ad_config_guide.html>`__,
and the `settings reference
<https://django-auth-adfs.readthedocs.io/en/stable/settings_ref.html#tenant-id>`__
for ``TENANT_ID`` and its neighbours. They will be ahead of this page.

.. warning::

    **We have not been able to test this path.** The project has no Entra
    tenant, so the settings above are derived from the library's own behaviour
    and from Microsoft's documented claim names rather than from a working
    QATrack+ deployment. Group names in particular may arrive as GUIDs rather
    than names depending on how the app registration is configured, which
    affects :ref:`Active Directory group mapping <ad_group_map>`.

    If you are running QATrack+ against Microsoft 365, **please tell us what
    you had to change** - https://github.com/qatrackplus/qatrackplus/issues or
    https://groups.google.com/g/qatrack.


.. _ad_group_map:

Mapping Active Directory Groups to QATrack+ Groups
--------------------------------------------------

You can have your users automatically added to one or more :ref:`QATrack+
groups <auth_groups>` based on their Active Directory Group memberships.  For
more information on configuring this see :ref:`Active Directory Group to
QATrack+ Groups Map <auth_ad_groups>`.

.. warning::

    **Two kinds of group membership QATrack+ does not see.** Both are measured
    against a real directory, and both affect every version of Active
    Directory - they are not a new-release problem.

    **A group that is somebody's primary group.** Active Directory does not
    list a user's primary group in the ``memberOf`` attribute, and ``memberOf``
    is what QATrack+ reads. So if you mark a group as an *account qualifying
    group* and it is also a user's primary group, **that user cannot sign in** -
    QATrack+ concludes they belong to no qualifying group. The log says exactly
    that, which reads like a directory problem rather than a configuration one.

    **A group reached only through another group.** Membership is read as the
    directory reports it, not followed up the chain. A user in *Sub-Physics*,
    where *Sub-Physics* is itself a member of your qualifying group
    *Physics*, is refused - and mapped groups are missed the same way.

    **So: make a qualifying group one that users are direct members of, and not
    anybody's primary group.** A dedicated group created for the purpose
    satisfies both, which is why most sites never meet this.

    Both are defects rather than decisions and we intend to fix them; neither
    has a workaround beyond the advice above. If you have an Active Directory
    where this matters - deep group nesting, or primary groups used
    meaningfully - **please tell us**, because the shape of your directory is
    the part we cannot reproduce.


