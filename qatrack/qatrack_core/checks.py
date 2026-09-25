import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.checks import Error, register


@register()
def check_media_folder_permissions(app_configs, **kwargs):
    errors = []
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    
    # Check if MEDIA_ROOT is configured and if the directory exists
    # This check is very likely unnecessary, since Django appears to recreate the folder on manage.py check, but it is here for completeness.

    if not media_root:
        errors.append(Error("The Media folder is not configured"))
        return errors
        
    media_root_path = Path(media_root)

    if not media_root_path.exists():
        errors.append(Error(f"The Media folder '{media_root}' does not exist"))
        return errors
    # End of redundant check    
    
    uploads_dirs = [
        media_root_path,
        media_root_path / 'uploads',
        media_root_path / 'uploads' / 'tmp',
    ]
    

    for directory in uploads_dirs:
        if directory.exists():
            if not directory.is_dir() or not os.access(directory, os.W_OK):
                errors.append(
                    Error(
                        f"The Django server process does not have write permissions to '{directory}'.",
                        hint=f"Check folder permissions. You may need to run `sudo chown -R www-data:www-data {media_root}` and `sudo chmod -R 775 {media_root}` (replace www-data with your web server user).",
                        id='qatrack.E001',
                    )
                )
            else:
                try:
                    fd, temp_path = tempfile.mkstemp(dir=str(directory))
                    os.close(fd)
                    Path(temp_path).unlink()
                except Exception as e:
                    errors.append(
                        Error(
                            f"The Django server process could not create a file in '{directory}': {e}",
                            hint="Check folder permissions and disk space.",
                            id='qatrack.E002',
                        )
                    )
        else:
            parent = directory.parent
            if parent.exists() and not os.access(parent, os.W_OK):
                errors.append(
                    Error(
                        f"The Django server process does not have write permissions to '{parent}' to create '{directory}'.",
                        hint=f"Check folder permissions. You may need to run `sudo chown -R www-data:www-data {media_root}`.",
                        id='qatrack.E001',
                    )
                )
    return errors


# The two backends that call into python-ldap. django-auth-ldap's own backend
# is listed too, for sites that use it directly rather than through ours.
LDAP_DEPENDENT_BACKENDS = {
    'qatrack.accounts.backends.ActiveDirectoryGroupMembershipSSLBackend',
    'qatrack.accounts.backends.WindowsIntegratedAuthenticationBackend',
    'django_auth_ldap.backend.LDAPBackend',
}


@register()
def check_ldap_backend_dependencies(app_configs, **kwargs):
    """Fail loudly when an LDAP backend is configured but python-ldap is absent.

    `qatrack/accounts/backends.py` opens with

        try:
            import ldap
        except ImportError:
            pass

    so a missing python-ldap is swallowed at import time. The backend class
    still loads, Django still lists it in AUTHENTICATION_BACKENDS, and the
    failure surfaces only when somebody tries to log in - as a NameError deep
    in an authentication path, on a clinical system, to a user who cannot get
    in and an administrator with no obvious cause.

    It is reachable without anyone doing anything wrong. python-ldap is only
    pulled in by the `mssql` extra, so a site following the Linux install guide
    (`uv sync --extra postgres`) and then configuring Active Directory has no
    ldap module and no indication of it.

    An Error rather than a Warning: unlike the unique-constraint check, nothing
    here is made worse by refusing to start. A deployment whose only
    authentication path cannot work is not in a state where running is better
    than stopping, and the fix is one install command away.
    """
    configured = set(getattr(settings, 'AUTHENTICATION_BACKENDS', None) or [])
    needs_ldap = sorted(configured & LDAP_DEPENDENT_BACKENDS)
    if not needs_ldap:
        return []

    try:
        import ldap  # noqa: F401
    except ImportError:
        return [
            Error(
                "AUTHENTICATION_BACKENDS includes %s, which needs python-ldap, "
                "but it is not installed." % ', '.join(needs_ldap),
                hint=(
                    "Install it with the extra that provides it:\n\n"
                    "    uv sync --extra ldap\n\n"
                    "or, on releases where it ships inside the SQL Server extra:\n\n"
                    "    uv sync --extra mssql\n\n"
                    "On Linux python-ldap builds from source and needs "
                    "libldap2-dev and libsasl2-dev. Without it these backends "
                    "load but fail at login, because the import error is "
                    "swallowed in qatrack/accounts/backends.py."
                ),
                id='qatrack.E003',
            )
        ]
    return []
