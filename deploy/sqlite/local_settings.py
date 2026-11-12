# Set to True to enable debug mode (not safe for regular use!)
DEBUG = False

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

# CSRF_TRUSTED_ORIGINS is required for Django 4.0+. It must include the scheme (http/https).
CSRF_TRUSTED_ORIGINS = ['http://XX.XXX.XXX.XX', 'https://XX.XXX.XXX.XX']

# Set to False to disable the SQL Query Tool
USE_SQL_REPORTS =  True

# If you host your QATrack+ instance at a non root url (e.g. 12.345.678.9/qatrack)
# then you need to uncomment (and possibly modify) the following settings
# FORCE_SCRIPT_NAME = "/qatrack"
# LOGIN_EXEMPT_URLS does NOT need changing for a non-root deployment, and must
# not be given a "/qatrack" prefix. LoginRequiredMiddleware matches
# request.path_info, which is URLconf-relative - FORCE_SCRIPT_NAME affects
# generated URLs, not path_info - so the default patterns in settings.py already
# work here. Prefixed patterns match nothing, which would leave even the login
# page unexempt.
# LOGIN_REDIRECT_URL = '/qatrack/qa/unit/'
# LOGIN_URL = "/qatrack/accounts/login/"


# Who to email when server errors occur
ADMINS = (
    ('Admin Name', 'YOUR_EMAIL_ADDRESS_GOES_HERE'),
)
MANAGERS = ADMINS

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Toronto'


# Precision to use when displaying constant values
CONSTANT_PRECISION = 8


# This is the warning message given to the user when a test result is out of tolerance
# Override this setting in local_settings.py to a locally relevant warning message
DEFAULT_WARNING_MESSAGE = "Do not treat"


# Display ordering on the "Choose Unit" page. (Use "name" or "number")
ORDER_UNITS_BY = "number"

# Enable or disable the "Difference" column when reviewing test lists
REVIEW_DIFF_COL = False

# default display settings for test statuses
TEST_STATUS_DISPLAY = {
    'fail': "Fail",
    'not_done': "Not Done",
    'done': "Done",
    'ok': "OK",
    'tolerance': "Tolerance",
    'action': "Action",
    'no_tol': "No Tol Set",
}

# default short display settings for test statuses
TEST_STATUS_DISPLAY_SHORT = {
    'fail': "Fail",
    'not_done': "Not Done",
    'done': "Done",
    'ok': "OK",
    'tolerance': "TOL",
    'action': "ACT",
    'no_tol': "NO TOL",
}


# Email and notification settings
EMAIL_NOTIFICATION_USER = None
EMAIL_NOTIFICATION_PWD = None
EMAIL_NOTIFICATION_TEMPLATE = "notification_email.html"
EMAIL_NOTIFICATION_SENDER = "qatrack@yourmailhost.com"
# use either a static subject or a customizable template
# EMAIL_NOTIFICATION_SUBJECT = "QATrack+ Test Status Notification"
EMAIL_NOTIFICATION_SUBJECT_TEMPLATE = "notification_email_subject.txt"

EMAIL_FAIL_SILENTLY = True
EMAIL_HOST = ""  # e.g. 'smtp.gmail.com'
EMAIL_HOST_USER = ''  # e.g. "randle.taylor@gmail.com"
EMAIL_HOST_PASSWORD = 'your_password_here'
EMAIL_USE_TLS = True
EMAIL_PORT = 587


# ------------------------------------------------------------------------------
# Dates and times
#
# Default: YYYY-MM-DD HH:MM, in every language, and the date pickers write the
# same format they display. Set the format here and everything follows from it -
# display, pickers, and the help text under each date field. Python strptime
# syntax (%Y year, %m month, %d day, %H hour, %M minute).
#
# QATRACK_DATETIME_FORMAT = "%Y/%m/%d %H:%M"   # 2012/05/31 14:30
# QATRACK_DATE_FORMAT = "%Y/%m/%d"             # 2012/05/31
# QATRACK_TIME_FORMAT = "%H:%M"
#
# What people may *type* is separate from what is displayed, and adding to it
# changes nothing anybody sees:
#
# QATRACK_EXTRA_DATETIME_INPUT_FORMATS = ["%d %b %Y %H:%M", "%d/%m/%Y %H:%M"]
# QATRACK_EXTRA_DATE_INPUT_FORMATS = ["%d %b %Y", "%Y/%m/%d"]
#
# All-numeric day/month orders are not blocked, but warn at startup
# (qatrack.W004): 03/05/2026 is a different day depending on who reads it, and a
# QC record is read by people trained in different conventions. The JSON API's
# format is fixed and is unaffected by any of this.
#
# See "Date and Time Format Settings" in docs/install/config.rst.
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
# Authentication
#
# The default is QATrack+'s own user database: nothing to configure here.
#
# For Active Directory, AD FS or Microsoft 365 / Entra ID, see "Authentication
# Backends" in the installation documentation. It covers which backend suits
# which deployment, the settings each needs, and the two things most likely to
# catch you out: Entra ID does not answer LDAP binds, and encrypting the
# connection is not optional on a current domain controller.
#
# Three things worth knowing before you start, because the symptoms do not point
# at the cause:
#
#  * Keep a local account you can sign in with, and record its password
#    somewhere other than QATrack+.
#  * Use LDAPS on port 636. A domain controller with LDAP signing enforced -
#    the default Microsoft has pushed since 2020 - refuses an unencrypted bind,
#    and all QATrack+ can report is "Unable to contact LDAP server".
#  * On Linux, install python-ldap through the `ldap` extra rather than by hand;
#    `uv sync` removes anything it was not told to keep. Without the package,
#    once an LDAP backend is configured, nobody can sign in at all - not just
#    directory users.
#
# For the AUTH_ADFS keys and for registering the application on the identity
# provider, see django-auth-adfs's own documentation:
#   settings reference   https://django-auth-adfs.readthedocs.io/en/latest/settings_ref.html
#   Entra ID / Azure AD  https://django-auth-adfs.readthedocs.io/en/latest/azure_ad_config_guide.html
#   on-prem AD FS 4.0    https://django-auth-adfs.readthedocs.io/en/latest/adfs_4.0_config_guide.html
#   troubleshooting      https://django-auth-adfs.readthedocs.io/en/latest/troubleshooting.html
#
# NOT YET IDEALLY TESTED: the Microsoft 365 / Entra ID path. The project has no
# tenant, so those instructions come from the library's behaviour and
# Microsoft's documented claim names rather than from a working deployment.
# Please tell us what you had to change:
# https://github.com/qatrackplus/qatrackplus/issues
# ------------------------------------------------------------------------------
