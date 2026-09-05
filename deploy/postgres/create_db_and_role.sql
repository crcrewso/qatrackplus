-- SECURITY: 'qatrackpass' is a public, documented example password, not a
-- secret. Change it here and in the matching deploy/postgres/local_settings.py
-- before deploying to production.
CREATE USER qatrack WITH PASSWORD 'qatrackpass';
CREATE DATABASE qatrackplus OWNER qatrack;
GRANT ALL PRIVILEGES ON DATABASE qatrackplus to qatrack;
