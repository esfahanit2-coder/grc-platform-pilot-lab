.PHONY: up down build logs test backend-shell migrate makemigrations frontend-lint

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

test:
	docker compose run --rm backend python manage.py test

backend-shell:
	docker compose run --rm backend python manage.py shell

migrate:
	docker compose run --rm backend python manage.py migrate

makemigrations:
	docker compose run --rm backend python manage.py makemigrations

frontend-lint:
	docker compose run --rm frontend npm run lint
