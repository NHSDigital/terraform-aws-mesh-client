import json
import os
from collections.abc import Generator
from typing import Literal, cast
from uuid import uuid4

import pytest
from integration.test_helpers import temp_env_vars
from mesh_client import MeshClient
from moto import mock_aws
from mypy_boto3_dynamodb import DynamoDBClient
from mypy_boto3_s3 import S3Client
from mypy_boto3_stepfunctions import SFNClient
from nhs_aws_helpers import (
    dynamodb_client as _ddb_client,
)
from nhs_aws_helpers import (
    s3_client as _s3_client,
)
from nhs_aws_helpers import (
    ssm_client as _ssm_client,
)
from nhs_aws_helpers import (
    stepfunctions,
)
from shared.common import LockDetails, acquire_lock

from mocked.mesh_testing_common import (
    LOCAL_MAILBOXES,
    MB,
    SANDBOX_URL,
    reset_sandbox_mailbox,
)


@pytest.fixture(scope="module", autouse=True)
def _mock_aws():
    with mock_aws():
        yield


@pytest.fixture(name="s3_client")
def s3_client(_mock_aws) -> S3Client:
    return _s3_client()


@pytest.fixture(name="ddb_client")
def ddb_client(_mock_aws) -> DynamoDBClient:
    return _ddb_client()


@pytest.fixture
def mocked_lock_table(ddb_client: DynamoDBClient, environment):
    """
    Create a temporary lock table and delete after use.
    """
    table_name = os.getenv("DDB_LOCK_TABLE_NAME") or "mocked-lock-table"
    ddb_client.create_table(
        AttributeDefinitions=[
            {"AttributeName": "LockOwner", "AttributeType": "S"},
            {"AttributeName": "LockType", "AttributeType": "S"},
            {"AttributeName": "LockName", "AttributeType": "S"},
        ],
        TableName=table_name,
        KeySchema=[{"AttributeName": "LockName", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "LockTypeOwnerTableIndex",
                "KeySchema": [
                    {"AttributeName": "LockType", "KeyType": "HASH"},
                    {"AttributeName": "LockOwner", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "KEYS_ONLY"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    yield ddb_client.describe_table(TableName=table_name).get("Table", None)

    ddb_client.delete_table(TableName=table_name)


@pytest.fixture
def create_lock_row(ddb_client: DynamoDBClient, mocked_lock_table):
    """
    Use a "fixture as a factory" pattern so we can pre-seed multiple lock rows, track their details and delete them
    afterwards.
    """
    created_rows: list[LockDetails] = []

    def _create_lock_row() -> LockDetails:
        lock_name = uuid4().hex
        execution_id = uuid4().hex
        new_row = acquire_lock(ddb_client, lock_name, execution_id)
        created_rows.append(new_row)
        return new_row

    yield _create_lock_row

    for created_row in created_rows:
        ddb_client.delete_item(
            TableName=mocked_lock_table["TableName"],
            Key={"LockName": {"S": created_row.LockName}},
        )


@pytest.fixture
def environment(
    _mock_aws,
) -> Generator[str, None, None]:
    environment = uuid4().hex
    with temp_env_vars(
        ENVIRONMENT=environment,
        AWS_REGION="eu-west-2",
        AWS_EXECUTION_ENV="AWS_Lambda_python3.8",
        AWS_LAMBDA_FUNCTION_NAME="lambda_test",
        AWS_LAMBDA_FUNCTION_MEMORY_SIZE="128",
        AWS_LAMBDA_FUNCTION_VERSION="1",
        MESH_URL="https://localhost:8700",
        MESH_BUCKET=f"{environment}-mesh",
        SEND_MESSAGE_STEP_FUNCTION_ARN=f"arn:aws:states:eu-west-2:123456789012:stateMachine:{environment}-send-message",
        GET_MESSAGES_STEP_FUNCTION_ARN=f"arn:aws:states:eu-west-2:123456789012:stateMachine:{environment}-get-messages",
        CA_CERT_CONFIG_KEY=f"/{environment}/mesh/MESH_CA_CERT",
        CLIENT_CERT_CONFIG_KEY=f"/{environment}/mesh/MESH_CLIENT_CERT",
        CLIENT_KEY_CONFIG_KEY=f"/{environment}/mesh/MESH_CLIENT_KEY",
        SHARED_KEY_CONFIG_KEY=f"/{environment}/mesh/MESH_SHARED_KEY",
        MAILBOXES_BASE_CONFIG_KEY=f"/{environment}/mesh/mailboxes",
        VERIFY_CHECKS_COMMON_NAME=False,
        DDB_LOCK_TABLE_NAME="mocked-lock-table",
    ):
        yield environment


@pytest.fixture
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
        Key="X26ABC2/outbound/testfile.json",
        Body=file_content,
        Metadata={
            "Mex-subject": "Custom Subject",
        },
    )
    return bucket


@pytest.fixture
def send_message_sfn_arn(environment: str) -> str:
    return _setup_step_function(
        stepfunctions(), environment, f"{environment}-send-message"
    )


@pytest.fixture
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
def _ssm_config(environment: str):
    ssm_client = _ssm_client()
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mapping/{environment}-mesh/X26ABC2/outbound/src_mailbox",
        value="X26ABC2",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mapping/{environment}-mesh/X26ABC2/outbound/dest_mailbox",
        value="X26ABC1",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mapping/{environment}-mesh/X26ABC2/outbound/workflow_id",
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
        name=f"/{environment}/mesh/mailboxes/X26ABC1/MAILBOX_PASSWORD",
        value="pwd123456",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/X26ABC1/INBOUND_BUCKET",
        value=f"{environment}-mesh",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/X26ABC1/INBOUND_FOLDER",
        value="inbound-X26ABC1",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/X26ABC2/MAILBOX_PASSWORD",
        value="pwd123456",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/X26ABC2/INBOUND_BUCKET",
        value=f"{environment}-mesh",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/mailboxes/X26ABC2/INBOUND_FOLDER",
        value="inbound-X26ABC2",
    )
    put_parameter(
        ssm_client,
        name=f"/{environment}/mesh/MESH_VERIFY_SSL",
        value="True",
    )
    with open(
        f"{os.path.dirname(__file__)}/../../scripts/self-signed-ca/bundles/server-sub-ca-bundle.pem"
    ) as f:
        put_parameter(
            ssm_client,
            name=f"/{environment}/mesh/MESH_CA_CERT",
            value=f.read(),
        )
    with open(
        f"{os.path.dirname(__file__)}/../../scripts/self-signed-ca/certs/client/valid/crt.pem"
    ) as f:
        put_parameter(
            ssm_client,
            name=f"/{environment}/mesh/MESH_CLIENT_CERT",
            value=f.read(),
        )
    with open(
        f"{os.path.dirname(__file__)}/../../scripts/self-signed-ca/certs/client/valid/key.pem"
    ) as f:
        put_parameter(
            ssm_client,
            name=f"/{environment}/mesh/MESH_CLIENT_KEY",
            value=f.read(),
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


@pytest.fixture(name="mesh_client_one")
def get_mesh_client_one() -> Generator[MeshClient, None, None]:
    with MeshClient(
        url=SANDBOX_URL,
        mailbox=LOCAL_MAILBOXES[0],
        password="pwd123456",
        shared_key=b"TestKey",
        verify=False,
        max_chunk_size=10 * MB,
    ) as client:
        reset_sandbox_mailbox(client._mailbox)
        yield client


@pytest.fixture(name="mesh_client_two")
def get_mesh_client_two() -> Generator[MeshClient, None, None]:
    with MeshClient(
        url=SANDBOX_URL,
        mailbox=LOCAL_MAILBOXES[1],
        password="pwd123456",
        shared_key=b"TestKey",
        verify=False,
        max_chunk_size=10 * MB,
    ) as client:
        reset_sandbox_mailbox(client._mailbox)
        yield client
