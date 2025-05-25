export COMPOSE_FILE ?= docker-compose.yml
export VERSION := $(shell git describe --tags --exact-match 2>/dev/null || echo beta)

.PHONY: down
down:
	rm up || true
	rm dep || true
	docker-compose down || true

build:
	docker-compose build
	echo "" > build

up: build
	docker-compose up -d
	echo "" > up

deps: up
	docker-compose exec ${CI_DC_DISABLE_TTY} e2e python3 -m venv /venv
	docker-compose exec ${CI_DC_DISABLE_TTY} e2e /venv/bin/python3 -m pip install --upgrade pip
	docker-compose exec ${CI_DC_DISABLE_TTY} e2e /venv/bin/python3 -m pip install -r requirements.txt
	docker-compose exec ${CI_DC_DISABLE_TTY} e2e /venv/bin/python3 -m pip install /uber-compose
	echo "" > deps

.PHONY: e2e-run
e2e-run: up deps
	docker-compose exec ${CI_DC_DISABLE_TTY} e2e /venv/bin/python3 -m vedro run $(args)
