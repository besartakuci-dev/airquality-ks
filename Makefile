.PHONY: up down logs test migrate

COMPOSE := docker compose

## Build images and start every service in the background
up:
	$(COMPOSE) up -d --build

## Stop and remove containers (data in named volumes is kept)
down:
	$(COMPOSE) down

## Follow logs from all services (make logs s=api for one service)
logs:
	$(COMPOSE) logs -f $(s)

## Run the API test suite locally (pip install -r api/requirements-dev.txt first)
test:
	python -m pytest

## Apply database migrations inside the api container
migrate:
	$(COMPOSE) run --rm -v ./db:/db -w /db api alembic upgrade head
