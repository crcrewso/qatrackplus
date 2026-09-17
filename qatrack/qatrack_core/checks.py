import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Warning, register


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


@register()
def check_deprecated_email_notification_settings(app_configs, **kwargs):
    # EMAIL_NOTIFICATION_USER/PWD were replaced by the standard Django
    # EMAIL_HOST_USER/EMAIL_HOST_PASSWORD settings. settings.py still copies
    # them over for anyone upgrading from an older local_settings.py, but
    # that shim is silent - this check gives upgrading deployers a visible
    # nudge to switch over rather than leaving them on a deprecated path
    # indefinitely.
    warnings = []
    if getattr(settings, 'EMAIL_NOTIFICATION_USER', None) or getattr(settings, 'EMAIL_NOTIFICATION_PWD', None):
        warnings.append(
            Warning(
                "EMAIL_NOTIFICATION_USER/EMAIL_NOTIFICATION_PWD are deprecated.",
                hint="Rename these to EMAIL_HOST_USER/EMAIL_HOST_PASSWORD in your local_settings.py.",
                id='qatrack.W001',
            )
        )
    return warnings


# Placeholder values shipped in the deploy/*/local_settings.py templates. If any
# of these survive into a running instance, the template was copied but not
# finished.
_HOST_PLACEHOLDERS = ('XX.XXX.XXX.XX', 'YOUR_HOST_NAME_HERE')
_SECRET_PLACEHOLDERS = ('your_password_here', 'qatrackpass', 'change_me')


@register()
def check_unedited_placeholders(app_configs, **kwargs):
    """Catch deploy templates that were copied but never filled in.

    `import *` means an unedited placeholder is indistinguishable from a
    deliberate value - nothing validates it, and ALLOWED_HOSTS = ['XX.XXX.XXX.XX']
    fails at request time with a confusing DisallowedHost rather than at
    startup with something actionable.
    """
    problems = []

    for name in ('ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS'):
        values = getattr(settings, name, None) or []
        stale = [v for v in values if any(p in str(v) for p in _HOST_PLACEHOLDERS)]
        if stale:
            problems.append(
                Error(
                    "%s still contains the placeholder(s) shipped in the "
                    "deploy template: %s" % (name, ', '.join(repr(s) for s in stale)),
                    hint="Replace them with your server's host name or IP address "
                         "in qatrack/local_settings.py.",
                    id='qatrack.E002',
                )
            )

    # Credentials are a warning rather than an error: they are documented
    # example values, so an instance using them runs fine - it is just
    # using a password published in this repository.
    used = set()
    for db in (getattr(settings, 'DATABASES', None) or {}).values():
        pwd = str(db.get('PASSWORD', ''))
        used.update(p for p in _SECRET_PLACEHOLDERS if p and p == pwd)
    # Only when email is actually turned on: the templates ship
    # EMAIL_HOST_PASSWORD = 'your_password_here' commented-out alongside the
    # rest of the email block, and an instance with EMAIL_ENABLED off is not
    # using it for anything. Flagging it there would be noise.
    if getattr(settings, 'EMAIL_ENABLED', False):
        email_pwd = str(getattr(settings, 'EMAIL_HOST_PASSWORD', '') or '')
        used.update(p for p in _SECRET_PLACEHOLDERS if p and p == email_pwd)

    if used and not getattr(settings, 'DEBUG', False):
        problems.append(
            Warning(
                "A documented example password is in use: %s" % ', '.join(sorted(used)),
                hint="These values are published in this repository and in the "
                     "deploy/*/create_db_and_role.sql scripts. Change them to "
                     "something unique to your organization before clinical use.",
                id='qatrack.W002',
            )
        )

    return problems


def _suspect_setting_names(defined, known, cutoff=0.85):
    """Return [(defined_name, suggestion), ...] for probable typos.

    Split out from the check below so it can be tested without importing a
    real local_settings.py.

    Only names with a *close* match are reported. A deployer is free to define
    their own helper constants in local_settings.py, and those have no near
    neighbour among the real settings, so they stay silent. The cutoff is
    deliberately high - the goal is catching TIMEZONE for TIME_ZONE, not
    second-guessing anyone.
    """
    import difflib

    suspects = []
    for name in sorted(defined):
        if name in known:
            continue
        close = difflib.get_close_matches(name, known, n=1, cutoff=cutoff)
        if close:
            suspects.append((name, close[0]))
    return suspects


@register()
def check_local_settings_typos(app_configs, **kwargs):
    """Warn about names in local_settings.py that look like misspelt settings.

    `from .local_settings import *` silently accepts anything. Writing
    TIMEZONE instead of TIME_ZONE defines a new, unused name and leaves the
    real setting at its default - no error, no warning, and the symptom shows
    up much later as "why is my timezone wrong". Nothing else in the stack can
    catch this, because by the time settings are loaded the misspelling is
    indistinguishable from a deliberate constant.
    """
    try:
        from qatrack import local_settings
    except ModuleNotFoundError:
        # Absent under Docker (settings.py configures itself from the
        # environment and never imports it) and on a bare test run.
        return []

    from django.conf import global_settings

    from qatrack import settings as qatrack_settings

    known = {n for n in dir(global_settings) if n.isupper()}
    known |= {n for n in dir(qatrack_settings) if n.isupper()}
    defined = {n for n in dir(local_settings) if n.isupper()}

    return [
        Warning(
            "local_settings.py defines %s, which is not a QATrack+ or Django setting." % name,
            hint="Did you mean %s? If %s is your own constant, you can ignore this." % (
                suggestion, name),
            id='qatrack.W003',
        )
        for name, suggestion in _suspect_setting_names(defined, known)
    ]
