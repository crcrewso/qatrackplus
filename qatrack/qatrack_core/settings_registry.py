"""What happened to settings that moved, vanished or changed meaning.

Imports nothing - not Django, not the rest of QATrack+. ``scripts/
settings_report.py`` runs on deployments whose settings will not load at
all, so anything here has to be readable without a configured Django.

Four categories, because "is it still in settings.py?" answers none of them
on its own:

``REMOVED``
    Nothing reads the name any more. Safe to delete.

``RENAMED``
    Same job, new name.

``UNDECLARED_BUT_READ``
    Not declared in ``settings.py``, but code still reads it with a
    fallback. Setting it in ``local_settings.py`` still works. Telling a
    deployer to delete one of these would break a working configuration,
    which is why a purely mechanical check is not enough.

``DRIFTED``
    Same name, same type, different meaning or default. Undetectable by
    comparing names; the only reason this file is hand-maintained.

``test_settings_registry.py`` asserts each entry still matches the tree, so
the registry cannot rot quietly.
"""

REMOVED = {
    'UPLOADS_URL': {
        'version': '4.1',
        'why': "Nothing read it. Uploads are served from MEDIA_URL + 'uploads/'.",
        'action': "Delete the line.",
    },
    'SELENIUM_VIRTUAL_DISPLAY': {
        'version': '4.1',
        'why': "The test harness runs browsers headless; there is no virtual display to toggle.",
        'action': "Delete the line. Set SELENIUM_HEADLESS instead if you run the GUI tests.",
    },
}

RENAMED = {
    'CLEAN_USERNAME_STRING': {
        'new': 'ACCOUNTS_CLEAN_USERNAME_STRING',
        'version': '4.1',
        'note': (
            "The Active Directory and Windows integrated backends also accept "
            "AD_CLEAN_USERNAME_STRING. Setting either is enough."
        ),
    },
}

# Read via getattr(settings, name, default) in the module named below. Absent
# from settings.py on purpose - the default lives with the code that uses it.
UNDECLARED_BUT_READ = {
    name: {
        'read_by': 'qatrack/qatrack_core/management/commands/backup_site.py',
        'note': "Still honoured. Keep it if you set it deliberately.",
    }
    for name in (
        'BACKUP_DIR',
        'BACKUP_DB_DIR',
        'BACKUP_WEEKLY_DAY',
        'BACKUP_MONTHLY_DAY',
        'BACKUP_DAYS_TO_KEEP',
        'BACKUP_WEEKS_TO_KEEP',
        'BACKUP_MONTHS_TO_KEEP',
    )
}

DRIFTED = {
    'TIME_ZONE': {
        'version': '4.1',
        'was': "Defaulted to 'America/Toronto', so an unedited install silently ran on Toronto time.",
        'now': (
            "Ships as a placeholder that must be replaced. QATrack+ refuses to "
            "start until it is, on every platform."
        ),
        'action': "Set it to your clinic's zone, e.g. TIME_ZONE = 'America/Vancouver'.",
    },
    'SELENIUM_BROWSER': {
        'version': '4.1',
        'was': "Empty by default.",
        'now': "Defaults to 'firefox' and reads the SELENIUM_BROWSER environment variable first.",
        'action': "Only relevant if you run the GUI tests. No change needed otherwise.",
    },
}


def classify(name):
    """Return (category, detail) for a setting name, or (None, None)."""
    for category, table in (
        ('removed', REMOVED),
        ('renamed', RENAMED),
        ('undeclared_but_read', UNDECLARED_BUT_READ),
        ('drifted', DRIFTED),
    ):
        if name in table:
            return category, table[name]
    return None, None
