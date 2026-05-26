#!/bin/sh
set -e

# Wait for database
echo "Waiting for postgres..."
while ! pg_isready -h postgres -U postgres -d qatrackplus; do
  sleep 1
done
echo "PostgreSQL started"

export USE_DOCKER=true

echo "Creating cache table..."
python manage.py createcachetable

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn qatrack.wsgi:application -w 2 -b 0.0.0.0:8000
