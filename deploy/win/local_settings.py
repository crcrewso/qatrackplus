# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# If running in a Windows environment this must be set to the same as your system time zone.
TIME_ZONE = 'America/Toronto'

# All supported languages are enabled by default (see LANGUAGES/LANGUAGE_CODE
# in settings.py) - only set these here if you want to restrict which
# languages are available, or change the default. See the "Adding a New
# Language" tutorial in the docs for details.
# LANGUAGES = [('en', 'English'), ('fr', 'Français')]
# LANGUAGE_CODE = 'en'


# SECURITY: 'qatrackpass' below matches the example password used when
# creating the SQL Server logins in the install guide - it's a public,
# documented example value, not a secret. Change it (both here and when
# creating the logins in SSMS) to something unique to your organization
# before deploying to production.
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': 'qatrack',
        'USER': 'qatrack',
        'PASSWORD': 'qatrackpass',
        'HOST': '',  # leave blank unless using remote server or SQLExpress (use 127.0.0.1\\SQLExpress or COMPUTERNAME\\SQLExpress)
        'PORT': '',  # Set to empty string for default. Not used with sqlite3.
        'OPTIONS': {'driver': 'ODBC Driver 17 for SQL Server'},
    },
    'readonly': {
        'ENGINE': 'mssql',
        'NAME': 'qatrack',
        'USER': 'qatrack_reports',
        'PASSWORD': 'qatrackpass',
        'HOST': '',  # leave blank unless using remote server or SQLExpress (use 127.0.0.1\\SQLExpress or COMPUTERNAME\\SQLExpress)
        'PORT': '',  # Set to empty string for default. Not used with sqlite3.
        'OPTIONS': {'driver': 'ODBC Driver 17 for SQL Server'},
    },
}


# Set this to your server's hostname, e.g. ALLOWED_HOSTS = ['yourhostname']
# Find your Device Name via Windows Key + I -> System -> About.
ALLOWED_HOSTS = ['YOUR_HOST_NAME_HERE']
# If the database and the QATrack+ application are running on the same
# server, you'll likely also want to allow local access:
# ALLOWED_HOSTS = ['YOUR_HOST_NAME_HERE', '127.0.0.1', 'localhost']

# CSRF_TRUSTED_ORIGINS is required for Django 4.0+. It must include the scheme (http/https).
CSRF_TRUSTED_ORIGINS = ['http://YOUR_HOST_NAME_HERE', 'https://YOUR_HOST_NAME_HERE']
# ...and correspondingly, if allowing local access:
# CSRF_TRUSTED_ORIGINS = [
#     'http://YOUR_HOST_NAME_HERE', 'https://YOUR_HOST_NAME_HERE',
#     'http://127.0.0.1', 'https://127.0.0.1',
#     'http://localhost', 'https://localhost',
# ]

# Who to email when server errors occur
ADMINS = (('Admin Name', 'YOUR_EMAIL_ADDRESS_GOES_HERE'),)
MANAGERS = ADMINS

# Set to True to enable debug mode (not safe for regular use!)
DEBUG = False

# Set to False to disable the SQL Query Tool
USE_SQL_REPORTS = True

# needs to be set to True when running behind reverse proxy (normal deploy)
# set to False when not running behind reverse proxy
# Use True for e.g. CherryPy/IIS and False for Apache/mod_wsgi
USE_X_FORWARDED_HOST = True
# -----------------------------------------------------------------------------
# Backup settings - used by the `manage.py backup_site` command (currently
# only fully implemented for MSSQL and sqlite - not postgres or mysql).
# Adjust the path and schedule to suit your server; these particular values
# are also what backup_site falls back to if you remove this block entirely.
BACKUP_DIR = "C:\\deploy\\backups"
BACKUP_WEEKLY_DAY = 2  # 0 = Monday, 6 = Sunday (2 = Wednesday)
BACKUP_MONTHLY_DAY = 3
BACKUP_DAYS_TO_KEEP = 7
BACKUP_WEEKS_TO_KEEP = 5
BACKUP_MONTHS_TO_KEEP = 12


# If you host your QATrack+ instance at a non root url (e.g. 12.345.678.9/qatrack)
# then you need to uncomment (and possibly modify) the following settings
# FORCE_SCRIPT_NAME = "/qatrack"
# LOGIN_EXEMPT_URLS = [r"^qatrack/accounts/", r"qatrack/api/*"]
# LOGIN_REDIRECT_URL = '/qatrack/qa/unit/'
# LOGIN_URL = "/qatrack/accounts/login/"


# Precision to use when displaying constant values
CONSTANT_PRECISION = 8


# This is the warning message given to the user when a test result is out of tolerance
# Override this setting in local_settings.py to a locally relevant warning message
DEFAULT_WARNING_MESSAGE = 'Do not treat'


# Display ordering on the "Choose Unit" page. (Use "name" or "number")
ORDER_UNITS_BY = 'number'

# Enable or disable the "Difference" column when reviewing test lists
REVIEW_DIFF_COL = False

# default display settings for test statuses
TEST_STATUS_DISPLAY = {
    'fail': 'Fail',
    'not_done': 'Not Done',
    'done': 'Done',
    'ok': 'OK',
    'tolerance': 'Tolerance',
    'action': 'Action',
    'no_tol': 'No Tol Set',
}

# default short display settings for test statuses
TEST_STATUS_DISPLAY_SHORT = {
    'fail': 'Fail',
    'not_done': 'Not Done',
    'done': 'Done',
    'ok': 'OK',
    'tolerance': 'TOL',
    'action': 'ACT',
    'no_tol': 'NO TOL',
}


# Email and notification settings
EMAIL_NOTIFICATION_USER = None
EMAIL_NOTIFICATION_PWD = None
EMAIL_NOTIFICATION_TEMPLATE = 'notification_email.html'
EMAIL_NOTIFICATION_SENDER = 'qatrack@yourmailhost.com'
# use either a static subject or a customizable template
# EMAIL_NOTIFICATION_SUBJECT = "QATrack+ Test Status Notification"
EMAIL_NOTIFICATION_SUBJECT_TEMPLATE = 'notification_email_subject.txt'

EMAIL_FAIL_SILENTLY = True
EMAIL_HOST = ''  # e.g. 'smtp.gmail.com'
EMAIL_HOST_USER = ''  # e.g. "randle.taylor@gmail.com"
EMAIL_HOST_PASSWORD = 'your_password_here'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
