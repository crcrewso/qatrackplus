-- SECURITY: 'qatrackpass' is a public, documented example password, not a
-- secret. Change it here and in the matching deploy/mysql/local_settings.py
-- before deploying to production.
CREATE USER 'qatrack'@'localhost' IDENTIFIED BY 'qatrackpass';
CREATE DATABASE qatrackplus CHARACTER SET utf8mb4;
GRANT ALL ON qatrackplus.* TO 'qatrack'@'localhost';
flush privileges;

