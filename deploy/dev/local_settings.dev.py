# Local development settings - copy this file to qatrack/local_settings.py
# and customize as needed. This template is for local development only; if
# you're setting up a real (production) deployment, use the template for
# your database engine under deploy/ instead (sqlite, postgres, mysql, win) -
# those default to DEBUG=False and require you to configure a real
# ALLOWED_HOSTS, rather than this file's permissive local-dev defaults.
#
# The point of this file is to let you override settings.py for your own
# environment without editing settings.py itself (which gets updated as the
# project evolves, and would overwrite your changes).

DEBUG = True # Local development only - do not use True in a real deployment!
TEMPLATE_DBG = True

# TIME_ZONE must be actively set - the placeholder in settings.py isn't a
# real time zone name, so Django refuses to start otherwise. Change this to
# your own time zone if you're not in Toronto.
TIME_ZONE = 'America/Toronto'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db/default.db',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}
DATABASES['readonly'] = DATABASES['default']

# Permissive for local development only. Every other deploy/*/local_settings.py
# template sets this explicitly (usually to a specific hostname) - this one
# was missing it entirely, which crashes `manage.py runserver` outright if
# DEBUG is ever set back to False here (Django requires ALLOWED_HOSTS to be
# set whenever DEBUG=False).
ALLOWED_HOSTS = ['*']

# Notification/report emails are disabled by default in dev so you don't
# need a real mail server to run the site, and so unconfigured email
# doesn't spam the console with loud failures during everyday development.
# Set this to True (and configure EMAIL_HOST etc. in settings.py's Email
# section) if you want to test real email sending locally.
EMAIL_ENABLED = False

# You can override anything in settings.py by defining it here
# I would recommend copying the portion of settings.py to this file and then modifying it
# as needed. This way it's easy to keep track of what has been changed, and they
# wont be lost when settings.py is updated in the future.
# Account and Email settings are a good place to start.

# Example:
#LANGUAGES = [('en', 'English'), ('fr', 'Français'), ('es', 'Español')]
#LANGUAGE_CODE = 'fr'

#AUTOSAVE_DAYS_TO_KEEP = 7
#MAX_TESTS_PER_TESTLIST = 100

#TODO - add default adfs settings here if needed

#CUSTOM_ROOT_PATH = "/path/to/your/qatrack/storage/directory"
#MEDIA_ROOT = os.path.join(CUSTOM_ROOT_PATH, "media")

#UPLOAD_PATH = "uploads"
#TMP_UPLOAD_PATH = os.path.join(UPLOAD_PATH, "tmp")
#UPLOAD_ROOT = os.path.join(MEDIA_ROOT, "uploads")
#TMP_UPLOAD_ROOT = os.path.join(UPLOAD_ROOT, "tmp")
#STATIC_ROOT = os.path.join(CUSTOM_ROOT_PATH, "static")
