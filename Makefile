VERSION=3.1.0
DATETIME=$(shell date '+%Y-%m-%d_%H-%M-%S')


dev-quickstart:
	cp -n deploy/dev/local_settings.dev.py qatrack/local_settings.py
	cp -n deploy/dev/local_test_settings.dev.py qatrack/local_test_settings.py
	mkdir -p db
	uv run python manage.py migrate
	uv run python manage.py createcachetable
	DJANGO_SUPERUSER_USERNAME=superuser DJANGO_SUPERUSER_PASSWORD=superuser DJANGO_SUPERUSER_EMAIL=superuser@example.com \
		uv run python manage.py createsuperuser --noinput

cover:
	uv run pytest --reuse-db --cov-report term-missing --cov ./ ${args}

cover-module:
	uv run pytest --cov-report term-missing --cov ./${module} ${module}

cover-mo:
	uv run pytest --reuse-db --cov-report term-missing:skip-covered --cov ./ ${args}

cover-qatrack:
	uv run pytest --reuse-db --cov-report term-missing --cov qatrack ${args}

test:
	uv run pytest ${args}

test_simple:
	uv run pytest -m "not selenium" ${args}

dumpdata:
	uv run python manage.py dumpdata \
		-v1 --indent=2 --natural-foreign --natural-primary \
		--output qatrack-dump-$(DATETIME).json

clearct:
	uv run python manage.py shell -c "from qatrack.qa.models import *; [m.objects.all().delete() for m in [ContentType, Tolerance, User]]"

flushdb:
	uv run python manage.py sqlflush | uv run python manage.py dbshell

format:
	uv run ruff format .

lint:
	uv run ruff check .

docs:
	cd docs && make html

docs-autobuild:
	uv run sphinx-autobuild docs docs/_build/html --port 8009

nginx.conf:
	sudo sed 's/YOURUSERNAMEHERE/$(USER)/g' deploy/nginx/qatrack.conf > qatrack.conf
	sudo mv qatrack.conf /etc/nginx/sites-available/qatrack.conf
	sudo ln -sf /etc/nginx/sites-available/qatrack.conf /etc/nginx/sites-enabled/qatrack.conf
	sudo usermod -a -G $(USER) www-data
	sudo service nginx restart

supervisor.conf:
	sudo sed 's/YOURUSERNAMEHERE/$(USER)/g' deploy/supervisor/django-q2.conf > django-q2.conf
	sudo sed 's/YOURUSERNAMEHERE/$(USER)/g' deploy/supervisor/gunicorn.conf > gunicorn.conf
	sudo mv django-q2.conf /etc/supervisor/conf.d/
	sudo mv gunicorn.conf /etc/supervisor/conf.d/
	sudo supervisorctl reread
	sudo supervisorctl update

schema:
	uv run python ./manage.py graph_models -a -g \
		-X Issue,IssueStatus,IssueType,IssuePriority,IssueTag \
		-o docs/developer/images/qatrack_schema_$(VERSION).svg

run:
	uv run python ./manage.py runserver

__cleardb__:
	uv run python manage.py shell -c "from qatrack.qa.models import *; TestListInstance.objects.all().delete(); UnitTestCollection.objects.all().delete(); ContentType.objects.all().delete()"

.PHONY: dev-quickstart cover cover-module cover-mo cover-qatrack test \
	test_simple dumpdata clearct flushdb format lint docs \
	docs-autobuild nginx.conf supervisor.conf schema run __cleardb__
