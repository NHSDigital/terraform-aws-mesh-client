import os
from collections.abc import Generator

import pytest
from mesh_client import MeshClient
from mypy_boto3_events import EventBridgeClient
from mypy_boto3_lambda import LambdaClient
from mypy_boto3_s3.service_resource import Bucket, S3ServiceResource
from mypy_boto3_secretsmanager import SecretsManagerClient
from mypy_boto3_ssm import SSMClient
from mypy_boto3_stepfunctions import SFNClient
from nhs_aws_helpers import (
    events_client,
    lambdas,
    s3_resource,
    secrets_client,
    ssm_client,
    stepfunctions,
)

# noinspection PyUnresolvedReferences
from nhs_aws_helpers.fixtures import *  # noqa: F403

from integration.constants import LOCAL_MAILBOXES, MB, SANDBOX_URL
from integration.test_helpers import reset_sandbox_mailbox


@pytest.fixture(scope="session", autouse=True)
def _global_setup():
    os.environ.setdefault("LOCAL_MODE", "True")
    os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4569")
    os.environ.setdefault("MESH_CLIENT_SHARED_KEY", "TestKey")
    os.environ.setdefault("SANDBOX_URL", SANDBOX_URL)


@pytest.fixture(autouse=True)
def _clean_mailboxes():
    for mailbox_id in LOCAL_MAILBOXES:
        reset_sandbox_mailbox(mailbox_id)


@pytest.fixture(name="mesh_client_one")
def get_mesh_client_one() -> Generator[MeshClient, None, None]:
    with MeshClient(
        url=SANDBOX_URL,
        mailbox=LOCAL_MAILBOXES[0],
        password="password",
        verify=False,
        max_chunk_size=10 * MB,
    ) as client:
        yield client


@pytest.fixture(name="mesh_client_two")
def get_mesh_client_two() -> Generator[MeshClient, None, None]:
    with MeshClient(
        url=SANDBOX_URL,
        mailbox=LOCAL_MAILBOXES[1],
        password="password",
        verify=False,
        max_chunk_size=10 * MB,
    ) as client:
        yield client


@pytest.fixture(scope="session")
def s3() -> S3ServiceResource:
    return s3_resource()


@pytest.fixture(scope="session")
def sfn() -> SFNClient:
    return stepfunctions()


@pytest.fixture(scope="session")
def ssm() -> SSMClient:
    return ssm_client()


@pytest.fixture(scope="session")
def secrets() -> SecretsManagerClient:
    return secrets_client()


@pytest.fixture(scope="session")
def events() -> EventBridgeClient:
    return events_client()


@pytest.fixture(scope="session", name="lambdas")
def get_lambdas() -> LambdaClient:
    return lambdas()


@pytest.fixture()
def local_mesh_bucket(s3: S3ServiceResource) -> Bucket:
    return s3.Bucket("local-mesh")
