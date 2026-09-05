-- SECURITY: 'qatrackpass' is a public, documented example password, not a
-- secret. Change it here and in the matching deploy/mysql/local_settings.py
-- before deploying to production.
CREATE USER 'qatrack_reports'@'localhost' IDENTIFIED BY 'qatrackpass';
GRANT SELECT ON qatrackplus.* to 'qatrack_reports'@'localhost';
