SHELL:=/bin/bash -O globstar
.SHELLFLAGS = -ec
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

clean:
	rm -f .certs.env || true
	rm -rf ca || true
	rm -rf certs || true
	rm -rf bundles || true
