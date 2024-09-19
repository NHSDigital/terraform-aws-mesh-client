import json
import os
from collections.abc import Callable
from datetime import datetime
from urllib.parse import quote_plus

from botocore.exceptions import ClientError
from mypy_boto3_dynamodb import DynamoDBClient
from mypy_boto3_secretsmanager import SecretsManagerClient
from mypy_boto3_ssm import SSMClient
from mypy_boto3_stepfunctions import SFNClient
from nhs_aws_helpers import secrets_client, ssm_client, stepfunctions

BOOL_TRUE_VALUES = ["yes", "true", "t", "y", "1"]
BOOL_FALSE_VALUES = ["no", "false", "f", "n", "0"]


class SingletonCheckFailure(Exception):
    """Singleton check failed"""

    def __init__(self, msg=None):
        super().__init__()
        self.msg = msg


class AwsFailedToPerformError(Exception):
    """Errors raised by AWS functions"""

    def __init__(self, msg=None):
        super().__init__()
        self.msg = msg


def nullsafe_quote(value: str | None) -> str:
    if not value:
        return ""

    return quote_plus(value, encoding="utf-8")


def strtobool(value, raise_exc=False):
    if isinstance(value, str):
        value = value.lower()
        if value in BOOL_TRUE_VALUES:
            return True
        if value in BOOL_FALSE_VALUES:
            return False

    if raise_exc:
        list_str = '", "'.join(BOOL_TRUE_VALUES + BOOL_FALSE_VALUES)
        raise ValueError(f'Expected "{list_str}"')
    return None


def acquire_lock(ddb_client: DynamoDBClient, lock_name: str, execution_id: str):
    """
    Attempt to take ownership of the semaphore row in the lock table.
    If the row already exists with an owner, then raise a SingletonCheckFailure.
    """
    lock_table_name = os.environ["DDB_LOCK_TABLE_NAME"]

    try:
        resp = ddb_client.update_item(
            ExpressionAttributeNames={"#LO": "LockOwner", "#AT": "AcquiredTime"},
            ExpressionAttributeValues={
                ":o": {"S": execution_id},
                ":t": {"S": str(datetime.now())},
            },
            UpdateExpression="SET #LO = :o, #AT = :t",
            TableName=lock_table_name,
            Key={"LockName": {"S": lock_name}},
            ConditionExpression="attribute_not_exists(LockOwner)",
        )
    except ClientError as ce:
        if ce.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise SingletonCheckFailure(f"Lock already exists for {lock_name}") from ce
    return resp.items


def singleton_check(
    step_function_arn: str,
    predicate: Callable[[dict], bool],
    sfn: SFNClient | None = None,
):
    """Find out whether there is another step function running for the same condition"""
    sfn = sfn or stepfunctions()

    if not step_function_arn or not step_function_arn.startswith("arn:aws:states:"):
        raise SingletonCheckFailure(
            f"No step function  for step_function_arn={step_function_arn}"
        )

    running_execution_arns: list[str] = []

    args = {"stateMachineArn": step_function_arn, "statusFilter": "RUNNING"}
    while True:
        response = sfn.list_executions(**args)  # type: ignore[arg-type]
        running_execution_arns.extend(
            execution["executionArn"]
            for execution in response["executions"]
            if execution["status"]
            == "RUNNING"  # localstack status-filter doesn't currently work
            # remove when merged: https://github.com/localstack/localstack/pull/9833
        )
        next_token = response.get("nextToken")
        if not next_token:
            break
        args["nextToken"] = next_token

    exec_count = 0
    for execution_arn in running_execution_arns:
        ex_response = sfn.describe_execution(executionArn=execution_arn)
        step_function_input = json.loads(ex_response.get("input", "{}"))

        if predicate(step_function_input):
            exec_count = exec_count + 1

        if exec_count > 1:
            raise SingletonCheckFailure("Process already running for this mailbox")

    return True


def convert_params_to_dict(params):
    """Convert ssm parameter dict to key:value dict"""
    new_dict = {}
    for entry in params:
        name = entry.get("Name", None)
        if name:
            var_name = os.path.basename(name)
            new_dict[var_name] = entry.get("Value", None)
    return new_dict


def return_failure(log_object, status, logpoint, mailbox, message=""):
    """Return a failure response with retry"""
    log_object.write_log(logpoint, None, {"mailbox": mailbox, "error": message})
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Retry-After": 18000,
        },
        "body": {
            "internal_id": log_object.internal_id,
            "error": message,
        },
    }


def get_params(
    parameter_names: set[str],
    secret_ids: set[str],
    decryption=True,
    ssm: SSMClient | None = None,
    secrets: SecretsManagerClient | None = None,
) -> dict[str, str]:
    """
    Get parameters from SSM and secrets manager
    """
    ssm = ssm or ssm_client()
    secrets = secrets or secrets_client()
    result = {}
    if parameter_names:
        params_result = ssm.get_parameters(
            Names=list(parameter_names), WithDecryption=decryption
        )
        for param in params_result.get("Parameters", []):
            result[param["Name"]] = param["Value"]

    if not secret_ids:
        return result

    if not decryption:
        raise ValueError("secret_ids requested but not with decryption")

    for secret_id in secret_ids:
        res = secrets.get_secret_value(SecretId=secret_id)
        result[secret_id] = res["SecretString"]

    return result
