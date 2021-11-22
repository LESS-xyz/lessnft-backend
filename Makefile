lines?=all

build:
	sudo docker-compose up --build -d 

test:
	sudo docker-compose exec web pytest --disable-pytest-warnings

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

scanner-build:
	sudo docker-compose up --build -d scanner
scanner-logs:
	sudo docker-compose logs -f --tail=$(lines) scanner
scanner-stop:
	sudo docker-compose stop scanner
