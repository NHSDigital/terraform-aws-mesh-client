import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _global_setup():
    os.environ.setdefault("LOCAL_MODE", "True")
    os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4766")
