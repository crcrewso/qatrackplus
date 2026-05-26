from .settings import DATABASES, USE_SQL_REPORTS
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deploy', 'docker'))
from docker_settings import *
if 'readonly' not in DATABASES and USE_SQL_REPORTS:
    DATABASES['readonly'] = DATABASES['default']
