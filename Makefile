setup-venv:
	if [ ! -d venv/ ] ; then python3.9 -m venv venv ; fi
	. venv/bin/activate && pip install -r mesh_client_aws_serverless/requirements.txt && pip install -r test-requirements.txt

build: setup-venv
	. venv/bin/activate && python -m build

test: setup-venv
	docker compose up -d && . venv/bin/activate && tox --recreate && docker compose down
