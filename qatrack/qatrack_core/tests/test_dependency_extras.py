"""An extra must install what its name says, and nothing a site cannot get.

`docs/install/win.rst` offers `pip install ".[win,mssql]"` as a fallback for a
Windows site that cannot run `uv` - restricted execution policy, or no outbound
access to astral.sh. That command could not complete, and the reason was not
visible from either end:

- the `mssql` extra carried `python-ldap` and `django-auth-ldap` as well as
  `mssql-django`;
- `python-ldap` publishes no Windows wheel, so this project pins one by URL in
  `[tool.uv.sources]`;
- **pip does not read `[tool.uv.sources]`** - it is a uv table, not a standard
  one - so pip resolved `python-ldap` from PyPI and fell back to building it from
  source, on the one platform the instruction is written for, whether or not the
  site used Active Directory.

The guide even anticipates the wheel, but at the wrong moment: its note tells an
AD site to `pip install` the wheel *after* the extras, and the failure is
*during* them.

So these tests assert the property the install command depends on: an extra names
the thing it is for. They read `pyproject.toml` rather than the environment,
because what is under test is what a site would be asked to resolve, not what
happens to be installed here.

See also: `django-auth-ldap` is not imported anywhere under `qatrack/`, which is
why it went rather than moved.
"""

import pathlib
import re
import tomllib

from django.conf import settings

REPO_ROOT = pathlib.Path(settings.PROJECT_ROOT).parent
LDAP_PACKAGES = {"python-ldap", "django-auth-ldap"}


def pyproject():
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def extras():
    return pyproject()["project"]["optional-dependencies"]


def names(requirements):
    """The distribution names in a requirements list, without versions or markers."""
    out = set()
    for req in requirements:
        head = req.split(";")[0].strip()
        for sep in ("[", ">", "<", "=", "!", "~", " "):
            head = head.split(sep)[0]
        out.add(head.strip().lower())
    return out


class TestTheMssqlExtraIsSqlServerOnly:

    def test_it_installs_the_sql_server_driver(self):
        assert "mssql-django" in names(extras()["mssql"])

    def test_it_pulls_in_no_ldap_package(self):
        """The defect: `pip install ".[win,mssql]"` could not resolve.

        Not a tidiness assertion. `python-ldap` here is what made the documented
        Windows fallback impossible, for every SQL Server site rather than only
        the ones using Active Directory.
        """
        found = names(extras()["mssql"]) & LDAP_PACKAGES
        assert not found, (
            "the mssql extra pulls %s again - `pip install \".[win,mssql]\"` in "
            "docs/install/win.rst cannot resolve python-ldap, because its only "
            "Windows wheel is pinned in [tool.uv.sources] and pip does not read "
            "that table. A SQL Server site that also uses AD wants --extra ldap "
            "as well." % ", ".join(sorted(found))
        )


class TestTheLdapExtraStillExists:
    """The control: the fix must move the problem, not delete the capability."""

    def test_it_provides_python_ldap(self):
        assert "python-ldap" in names(extras()["ldap"])

    def test_the_windows_wheel_is_still_pinned(self):
        """Removed from `mssql`, the pin is what `--extra ldap` depends on.

        A Windows AD site gets python-ldap through `uv`, from this URL. Losing
        the pin would send them to a PyPI source build - the same failure, moved.
        """
        sources = pyproject()["tool"]["uv"]["sources"]
        pin = sources["python-ldap"]

        assert pin["url"].endswith(".whl"), pin
        assert "win_amd64" in pin["url"], pin
        assert "win32" in pin["marker"], pin


class TestDjangoAuthLdapIsGone:
    """It went rather than moved, because nothing imports it."""

    def test_no_extra_declares_it(self):
        carriers = sorted(e for e, reqs in extras().items() if "django-auth-ldap" in names(reqs))
        assert not carriers, "django-auth-ldap is back, in: %s" % carriers

    def test_the_base_dependencies_do_not_either(self):
        assert "django-auth-ldap" not in names(pyproject()["project"]["dependencies"])

    def test_nothing_under_qatrack_imports_it(self):
        """The reason it could go at all - asserted, so a later import is caught.

        If somebody starts using django-auth-ldap, this fails and tells them to
        declare it rather than relying on it arriving through another extra,
        which is how it was reaching sites before.
        """
        # Import statements, not the bare name. The first version of this test
        # searched for the substring and found itself, which is the sort of pass
        # that looks like a failure and the sort of failure that looks like a
        # finding.
        pattern = re.compile(r"^\s*(?:from|import)\s+django_auth_ldap\b", re.M)
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in (REPO_ROOT / "qatrack").rglob("*.py")
            if pattern.search(path.read_text(encoding="utf-8", errors="replace"))
        ]
        assert not offenders, (
            "django_auth_ldap is imported in %s, but is no longer a declared "
            "dependency - declare it in an extra" % offenders
        )
