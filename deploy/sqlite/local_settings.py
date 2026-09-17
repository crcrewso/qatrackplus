# -----------------------------------------------------------------------------
# Settings you need to look at. Two kinds live here:
#
#   1. Settings with no usable default, marked below with an obvious
#      placeholder. QATrack+ will not start, or will misbehave, until you
#      replace them: TIME_ZONE, DATABASES, ALLOWED_HOSTS and
#      CSRF_TRUSTED_ORIGINS.
#
#   2. Settings this template states deliberately even though settings.py
#      already has a working default - DEBUG and USE_SQL_REPORTS. They are
#      marked "[template default]" below. You can leave them alone; change
#      them if the reasoning given does not match your site.
#
# Everything not in this section has a sensible default and lives commented
# out under "Optional settings" further down. See docs/install/config.rst
# for the full per-setting reference.

# [template default] settings.py already defaults DEBUG to False, so this
# line changes nothing. It is restated here because it is the single most
# security-relevant setting in the file, and a deployer should be able to
# confirm its value without going and reading settings.py.
# Set to True to enable debug mode (not safe for regular use!)
DEBUG = False

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Toronto'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',  # Add 'postgresql', 'mysql', 'sqlite3'
        'NAME': 'qatrackplus',  # Or path to database file if using sqlite3.
        'USER': '',  # Not used with sqlite3.
        'PASSWORD': '',  # Not used with sqlite3.
        'HOST': '',  # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',  # Set to empty string for default. Not used with sqlite3.
    },
    'readonly': {
        'ENGINE': 'django.db.backends.sqlite3',  # Add 'postgresql', 'mysql', 'sqlite3'
        'NAME': 'qatrackplus',  # Or path to database file if using sqlite3.
        'USER': '',  # Not used with sqlite3.
        'PASSWORD': '',  # Not used with sqlite3.
        'HOST': '',  # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',  # Set to empty string for default. Not used with sqlite3.
    }
}

# Change XX.XXX.XXX.XX to your servers IP address and/or host name e.g. ALLOWED_HOSTS = ['54.123.45.1', 'yourhostname']
ALLOWED_HOSTS = ['XX.XXX.XXX.XX']
# If the database and the QATrack+ application are running on the same
# server, you'll likely also want to allow local access:
# ALLOWED_HOSTS = ['XX.XXX.XXX.XX', '127.0.0.1', 'localhost']

# CSRF_TRUSTED_ORIGINS is required for Django 4.0+. It must include the scheme (http/https).
CSRF_TRUSTED_ORIGINS = ['http://XX.XXX.XXX.XX', 'https://XX.XXX.XXX.XX']
# ...and correspondingly, if allowing local access:
# CSRF_TRUSTED_ORIGINS = [
#     'http://XX.XXX.XXX.XX', 'https://XX.XXX.XXX.XX',
#     'http://127.0.0.1', 'https://127.0.0.1',
#     'http://localhost', 'https://localhost',
# ]

# [template default] settings.py defaults this to False; this template opts
# in. That is a real choice, not a formality: enabling it requires a
# 'readonly' database connection, which is why one is configured above. If
# you set this to False, the readonly block becomes unnecessary - and if you
# remove the readonly block while leaving this True, settings.py raises
# "Missing 'readonly' connection information" at startup.
# Set to False to disable the SQL Query Tool
USE_SQL_REPORTS = True


# -----------------------------------------------------------------------------
# Optional settings - QATrack+ runs fine with these left as-is. Uncomment and
# edit any of them to customize your installation.

# All supported languages are enabled by default (see LANGUAGES/LANGUAGE_CODE
# in settings.py) - only set these here if you want to restrict which
# languages are available, or change the default. See the "Adding a New
# Language" tutorial in the docs for details.
# LANGUAGES = [('en', 'English'), ('fr', 'Français')]
# LANGUAGE_CODE = 'en'

# If you host your QATrack+ instance at a non root url (e.g. 12.345.678.9/qatrack)
# then you need to uncomment (and possibly modify) the following settings
# FORCE_SCRIPT_NAME = "/qatrack"
# LOGIN_EXEMPT_URLS = [r"^qatrack/accounts/", r"qatrack/api/*"]
# LOGIN_REDIRECT_URL = '/qatrack/qa/unit/'
# LOGIN_URL = "/qatrack/accounts/login/"

# Who to email when server errors occur
# ADMINS = (
#     ('Admin Name', 'YOUR_EMAIL_ADDRESS_GOES_HERE'),
# )
# MANAGERS = ADMINS

# Precision to use when displaying constant values
# CONSTANT_PRECISION = 8

# This is the warning message given to the user when a test result is out of tolerance
# DEFAULT_WARNING_MESSAGE = "Do not treat"

# Display ordering on the "Choose Unit" page. (Use "name" or "number")
# ORDER_UNITS_BY = "number"

# Enable or disable the "Difference" column when reviewing test lists
# REVIEW_DIFF_COL = False

# default display settings for test statuses
# TEST_STATUS_DISPLAY = {
#     'fail': "Fail",
#     'not_done': "Not Done",
#     'done': "Done",
#     'ok': "OK",
#     'tolerance': "Tolerance",
#     'action': "Action",
#     'no_tol': "No Tol Set",
# }

# default short display settings for test statuses
# TEST_STATUS_DISPLAY_SHORT = {
#     'fail': "Fail",
#     'not_done': "Not Done",
#     'done': "Done",
#     'ok': "OK",
#     'tolerance': "TOL",
#     'action': "ACT",
#     'no_tol': "NO TOL",
# }

# Email and notification settings. EMAIL_ENABLED must be set to True once
# EMAIL_HOST etc. below are configured, or set explicitly to False if you
# don't want QATrack+ to send email at all - see qatrack_core.email for why
# this is a separate, explicit decision rather than implied by EMAIL_HOST.
# EMAIL_ENABLED = True
# EMAIL_NOTIFICATION_USER = None
# EMAIL_NOTIFICATION_PWD = None
# EMAIL_NOTIFICATION_TEMPLATE = "notification_email.html"
# EMAIL_NOTIFICATION_SENDER = "qatrack@yourmailhost.com"
# use either a static subject or a customizable template
# EMAIL_NOTIFICATION_SUBJECT = "QATrack+ Test Status Notification"
# EMAIL_NOTIFICATION_SUBJECT_TEMPLATE = "notification_email_subject.txt"
# EMAIL_FAIL_SILENTLY = True
# EMAIL_HOST = ""  # e.g. 'smtp.gmail.com'
# EMAIL_HOST_USER = ''  # e.g. "randle.taylor@gmail.com"
# EMAIL_HOST_PASSWORD = 'your_password_here'
# EMAIL_USE_TLS = True
# EMAIL_PORT = 587
