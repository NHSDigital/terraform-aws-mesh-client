SHELL:=/bin/bash -O globstar
.SHELLFLAGS = -ec
.PHONY: build dist
.DEFAULT_GOAL := list
# this is just to try and supress errors caused by poetry run
export PYTHONWARNINGS=ignore:::setuptools.command.install


list:
	@grep '^[^#[:space:]].*:' Makefile

guard-%:
	@ if [ "${${*}}" = "" ]; then \
		echo "Environment variable $* not set"; \
		exit 1; \
	fi

########################################################################################################################
##
## Makefile for this project things
##
########################################################################################################################
pwd := ${PWD}
dirname := $(notdir $(patsubst %/,%,$(CURDIR)))
DOCKER_BUILDKIT ?= 1

ifneq (,$(wildcard ./.env))
    include .env
    export
endif


install:
	poetry install --sync

install-ci:
	poetry install --without local --sync

update:
	poetry update

local-terraform:
	make -C stacks/localstack

docker-build:
	docker compose build --pull

up-ci: requirements certs
	docker compose up -d --remove-orphans
	scripts/wait-for-container.sh localstack
	make local-terraform

up: up-ci

stop-lambdas:
	docker stop $$(docker ps --filter name=lambda -q) || true

down: stop-lambdas
	poetry run docker compose down --remove-orphans || true
	make -C stacks/localstack clean

build:
	poetry run python -m build

pytest: certs
	poetry run pytest

test: pytest

tox:
	poetry run tox

tflint:
	@docker run -v "$(pwd)/module:/data" -v "$(pwd)/tflint.hcl:/tflint.hcl" --entrypoint=/bin/sh \
		ghcr.io/terraform-linters/tflint \
		-c "tflint --init --config '/tflint.hcl'; tflint --config '/tflint.hcl' --enable-plugin=aws"

tf-format-check:
	terraform fmt -check -recursive module

tf-format:
	terraform fmt --recursive

tfsec:
	tfsec module --config-file tfsec.yml

mypy:
	poetry run mypy .

shellcheck:
	@# Only swallow checking errors (rc=1), not fatal problems (rc=2)
	docker run --rm -i -v ${PWD}:/mnt:ro koalaman/shellcheck -f gcc -e SC1090,SC1091 `find . \( -path "*/.venv/*" -prune -o -path "*/build/*" -prune -o -path "*/.tox/*" -prune -o -path "*/java_client/*" -prune  \) -o -type f -name '*.sh' -print` || test $$? -eq 1

ruff: black
	poetry run ruff check . --fix --show-fixes

ruff-check:
	poetry run ruff check .

ruff-ci:
	poetry run ruff check . --output-format=github

lint: ruff mypy shellcheck tflint

black-check:
	poetry run black . --check

black:
	poetry run black .

coverage-cleanup:
	rm -f .coverage* || true

coverage-ci-test: certs
	poetry run coverage run -m pytest tests/integration --color=yes -v --junit-xml=./reports/junit/tests-integration.xml
	poetry run coverage run -a -m pytest tests/mocked --color=yes -v --junit-xml=./reports/junit/tests-mocked.xml

coverage-report:
	@poetry run coverage report; \
	poetry run coverage xml;

coverage: coverage-cleanup coverage-test coverage-report

coverage-test:
	poetry run coverage run -m pytest tests/integration
	poetry run coverage run -a -m pytest tests/mocked

coverage-ci: coverage-cleanup coverage-ci-test coverage-report

requirements:
	@lock_hash=$$(md5sum poetry.lock | cut -d' ' -f1); \
	for f in $$(find . -type f -name 'poetry-cmd.sh' | sort); do \
		reqs_dir="$$(dirname $$f)"; \
		echo "$${reqs_dir}"; \
		cmd_hash=$$(md5sum $$f | cut -d' ' -f1) ; \
		cur_hash=$$(cat "$${reqs_dir}/.lock-hash" 2>/dev/null || echo -n ''); \
		update="no"; \
		if test ! -f "$${reqs_dir}/requirements.txt"; then \
		  	echo "$${reqs_dir}/requirements.txt does not exist"; \
		  	update="yes"; \
		fi; \
		if [[ "$${lock_hash}+$${cmd_hash}" != "$${cur_hash}" ]]; then \
		  echo "$${lock_hash}+$${cmd_hash} != $${cur_hash}"; \
		  update="yes"; \
		fi; \
		if [[ "$${update}" == "yes" ]]; then \
		  echo "running: $${f}"; \
		  /bin/bash $$f; \
		  echo -n "$${lock_hash}+$${cmd_hash}" > "$${reqs_dir}/.lock-hash"; \
		else \
		  echo "$${lock_hash}+$${cmd_hash} == $${cur_hash}"; \
		fi \
	done

check-secrets:
	scripts/check-secrets.sh

check-secrets-all:
	scripts/check-secrets.sh unstaged

delete-hooks:
	rm .git/hooks/pre-commit 2>/dev/null || true
	rm .git/hooks/commit-msg 2>/dev/null || true

.git/hooks/pre-commit:
	cp scripts/hooks/pre-commit.sh .git/hooks/pre-commit

.git/hooks/commit-msg:
	cp scripts/hooks/commit-msg.sh .git/hooks/commit-msg

refresh-hooks: delete-hooks .git/hooks/pre-commit .git/hooks/commit-msg

certs:
	scripts/self-signed-ca/create-all.sh localhost

certs-new:
	rm -r resources/mesh_certs/local || true
	rm -f .docker.env || true
	scripts/self-signed-ca/create-all.sh localhost mesh_api --overwrite

scripts/self-signed-ca/.certs.env:
	make certs


pack-deps:
	module/pack-deps.sh ./module


pack-app: guard-env
	module/pack-app.sh ./module $(env)

list-functions:
	AWS_ENDPOINT_URL=http://localhost:4569 aws lambda list-functions | jq -r .Functions[].FunctionName

s3-ls:
	AWS_ENDPOINT_URL=http://localhost:4569 aws s3 ls --recursive s3://local-mesh/