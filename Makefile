lines?=all

build:
	sudo docker-compose up --build -d 

test:
	sudo docker-compose -f test.yml up --build --abort-on-container-exit

shell:
	sudo docker-compose exec web ./manage.py shell_plus

web-build:
	sudo docker-compose up --build -d web
web-logs:
	sudo docker-compose logs -f --tail=$(lines) web

full_migrate: makemigrations migrate
makemigrations:
	sudo docker-compose exec web ./manage.py makemigrations
migrate:
	sudo docker-compose exec web ./manage.py migrate

scanner-fbuild:
	sudo docker-compose up --build -d --force-recreate scanner
scanner-build:
	sudo docker-compose up --build -d scanner
scanner-logs:
	sudo docker-compose logs -f --tail=$(lines) scanner
scanner-stop:
	sudo docker-compose stop scanner

fixtures: web-build
	sudo docker-compose exec web python manage.py create_fixtures

pre-commit:
	pip install pre-commit --upgrade
	pre-commit install -t pre-commit -t prepare-commit-msg
