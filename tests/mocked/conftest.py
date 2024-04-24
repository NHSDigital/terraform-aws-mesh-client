import json
import os
import ssl
from collections.abc import Generator
from typing import Literal, cast
from uuid import uuid4

import pytest
from integration.test_helpers import temp_env_vars
from moto import mock_aws
from mypy_boto3_s3 import S3Client
from mypy_boto3_stepfunctions import SFNClient
from nhs_aws_helpers import (
    s3_client as _s3_client,
)
from nhs_aws_helpers import (
    ssm_client as _ssm_client,
)
from nhs_aws_helpers import (
    stepfunctions,
)
from pytest_httpserver import HTTPServer
from trustme import CA


@pytest.fixture(scope="module", autouse=True)
def _mock_aws():
    with mock_aws():
        yield


@pytest.fixture(name="s3_client")
def s3_client(_mock_aws) -> S3Client:
    return _s3_client()


@pytest.fixture(scope="session")
def ca() -> CA:
    return CA()


@pytest.fixture(scope="session")
def httpserver_ssl_context(ca: CA):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    localhost_cert = ca.issue_cert("localhost")
    localhost_cert.configure_cert(context)
    return context


@pytest.fixture(scope="module")
def _httpclient_ssl_context(ca: CA):
    with ca.cert_pem.tempfile() as ca_temp_path:
        ssl.create_default_context(cafile=ca_temp_path)


@pytest.fixture()
def environment(
    _mock_aws, httpserver: HTTPServer, ca: CA
) -> Generator[str, None, None]:
    environment = uuid4().hex
    with temp_env_vars(
        ENVIRONMENT=environment,
        AWS_REGION="eu-west-2",
        AWS_EXECUTION_ENV="AWS_Lambda_python3.8",
        AWS_LAMBDA_FUNCTION_NAME="lambda_test",
        AWS_LAMBDA_FUNCTION_MEMORY_SIZE="128",
        AWS_LAMBDA_FUNCTION_VERSION="1",
        CRUMB_SIZE="10",
        CHUNK_SIZE="10",
        MESH_URL=f"https://localhost:{httpserver.port}",
        MESH_BUCKET=f"{environment}-mesh",
        SEND_MESSAGE_STEP_FUNCTION_ARN=f"arn:aws:states:eu-west-2:123456789012:stateMachine:{environment}-send-message",
        GET_MESSAGES_STEP_FUNCTION_ARN=f"arn:aws:states:eu-west-2:123456789012:stateMachine:{environment}-get-messages",
        CA_CERT_CONFIG_KEY=f"/{environment}/mesh/MESH_CA_CERT",
        CLIENT_CERT_CONFIG_KEY=f"/{environment}/mesh/MESH_CLIENT_CERT",
        CLIENT_KEY_CONFIG_KEY=f"/{environment}/mesh/MESH_CLIENT_KEY",
        SHARED_KEY_CONFIG_KEY=f"/{environment}/mesh/MESH_SHARED_KEY",
        MAILBOXES_BASE_CONFIG_KEY=f"/{environment}/mesh/mailboxes",
    ):
        yield environment


@pytest.fixture()
def mesh_s3_bucket(s3_client: S3Client, environment: str) -> str:
    bucket = os.environ["MESH_BUCKET"]
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
    )
    FILE_CONTENT = "123456789012345678901234567890123"
    file_content = FILE_CONTENT
    s3_client.put_object(
        Bucket=f"{environment}-mesh",
        Key="MESH-TEST2/outbound/testfile.json",
        Body=file_content,
        Metadata={
            "Mex-subject": "Custom Subject",
        },
    )
    return bucket


@pytest.fixture()
def send_message_sfn_arn(environment: str) -> str:
    return _setup_step_function(
        stepfunctions(), environment, f"{environment}-send-message"
    )


@pytest.fixture()
def get_messages_sfn_arn(environment: str):
    return _setup_step_function(
        stepfunctions(), environment, f"{environment}-get-messages"
    )


def _setup_step_function(
    sfn_client: SFNClient, environment: str, step_function_name: str
) -> str:
    """Setup a mock step function with name from environment"""
    if not environment:
        environment = "default"
    step_func_definition = {
        "Comment": "Test step function",
        "StartAt": "HelloWorld",
        "States": {
            "HelloWorld": {
                "Type": "Task",
                "Resource": "arn:aws:lambda:eu-west-2:123456789012:function:HW",
                "End": True,
            }
        },
    }
    return cast(
        str,
        sfn_client.create_state_machine(
            definition=json.dumps(step_func_definition),
            loggingConfiguration={
                "destinations": [{"cloudWatchLogsLogGroup": {"logGroupArn": "xxx"}}],
                "includeExecutionData": False,
                "level": "ALL",
            },
            name=step_function_name,
            roleArn="arn:aws:iam::123456789012:role/StepFunctionRole",
            tags=[{"key": "environment", "value": environment}],
            tracingConfiguration={"enabled": False},
            type="STANDARD",
        )["stateMachineArn"],
    )


@pytest.fixture(autouse=True)
def _ssm_config(environment: str, ca: CA):
    ssm_client = _ssm_client()
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mapping/{environment}-mesh/MESH-TEST2/outbound/src_mailbox",
        value="MESH-TEST2",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mapping/{environment}-mesh/MESH-TEST2/outbound/dest_mailbox",
        value="MESH-TEST1",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mapping/{environment}-mesh/MESH-TEST2/outbound/workflow_id",
        value="TESTWORKFLOW",
    )
    # Setup secrets
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/MESH_URL",
        value="https://localhost",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/MESH_SHARED_KEY",
        value="TestKey",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/MESH-TEST1/MAILBOX_PASSWORD",
        value="pwd123456",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/MESH-TEST1/INBOUND_BUCKET",
        value=f"{environment}-mesh",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/MESH-TEST1/INBOUND_FOLDER",
        value="inbound-mesh-test1",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/MESH-TEST2/MAILBOX_PASSWORD",
        value="pwd123456",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/MESH-TEST2/INBOUND_BUCKET",
        value=f"{environment}-mesh",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/MESH-TEST2/INBOUND_FOLDER",
        value="inbound-mesh-test2",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/MESH_VERIFY_SSL",
        value="False",
    )
    # these are self signed certs
    ca_cert = ca.cert_pem.bytes().decode()

    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/MESH_CA_CERT",
        value=ca_cert,
    )
    client_key_cert = ca.issue_cert("localclient")
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/MESH_CLIENT_CERT",
        value=client_key_cert.cert_chain_pems[0].bytes().decode(),
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/MESH_CLIENT_KEY",
        value=client_key_cert.private_key_pem.bytes().decode(),
    )


def put_parameter(
    ssm_client,
    name: str,
    value: str,
    param_type: Literal["String", "SecureString", "StringList"] = "String",
    overwrite: bool = True,
):
    """Setup ssm param store for tests"""
    # Setup mapping
    ssm_client.put_parameter(
        Name=name, Value=value, Type=param_type, Overwrite=overwrite
    )
