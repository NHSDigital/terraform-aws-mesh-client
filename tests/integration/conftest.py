import os

import pytest
from mypy_boto3_s3.service_resource import Bucket, S3ServiceResource
from mypy_boto3_stepfunctions import SFNClient
from nhs_aws_helpers import s3_resource, stepfunctions

# noinspection PyUnresolvedReferences
from nhs_aws_helpers.fixtures import *  # noqa: F403


@pytest.fixture(scope="session", autouse=True)
def _global_setup():
    os.environ.setdefault("LOCAL_MODE", "True")
    os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4569")
    os.environ.setdefault("MESH_CLIENT_SHARED_KEY", "TestKey")
    os.environ.setdefault("SANDBOX_URL", "https://localhost:8700")


@pytest.fixture(scope="session")
def s3() -> S3ServiceResource:
    return s3_resource()


@pytest.fixture(scope="session")
def sfn() -> SFNClient:
    return stepfunctions()


@pytest.fixture()
def local_mesh_bucket(s3: S3ServiceResource) -> Bucket:
    return s3.Bucket("local-mesh")
