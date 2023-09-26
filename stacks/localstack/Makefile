SHELL:=/bin/bash -O globstar
.SHELLFLAGS = -ec
.PHONY: build dist
.DEFAULT_GOAL := apply

list:
	@grep '^[^#[:space:]].*:' Makefile

guard-%:
	@ if [ "${${*}}" = "" ]; then \
		echo "Environment variable $* not set"; \
		exit 1; \
	fi

clean:
	rm -f .terraform.plan 2>/dev/null || true
	rm -rf .terraform 2>/dev/null || true
	rm -rf terraform.tfstate.d 2>/dev/null || true
	rm -ff errored.tfstate 2>/dev/null || true
	rm -f .terraform.lock.hcl 2>/dev/null || true
	rm -f terraform.tfstate || true
	rm -f terraform.tfstate.backup || true

init:
	terraform init

maybe-init:
	@if [ ! -f terraform.tfstate ]; then \
		terraform init -upgrade; \
	fi

apply: maybe-init
	terraform apply -auto-approve

no-init: apply

plan:
	terraform plan

validate:
	@terraform validate -json | jq '.diagnostics[] | {detail: .detail, filename: .range.filename, start_line: .range.start.line}'

