import json
from uuid import uuid4

import pytest
from mypy_boto3_stepfunctions import SFNClient
from nhs_aws_helpers import lambdas

from .test_helpers import (
    CloudwatchLogsCapture,
    sync_json_lambda_invocation_successful,
    wait_for_execution_outcome,
    wait_till_not_running,
)

mailboxes = ["X26ABC1", "X26ABC2", "X26ABC3"]


_GET_MESSAGES_SFN_ARN = (
    "arn:aws:states:eu-west-2:000000000000:stateMachine:local-mesh-get-messages"
)
_FUNCTION_NAME = "local-mesh-poll-mailbox"
_LOG_GROUP = f"/aws/lambda/{_FUNCTION_NAME}"


@pytest.mark.parametrize("mailbox_id", mailboxes)
def test_invoke_get_messages_directly(mailbox_id: str):
    response = lambdas().invoke(
        FunctionName=_FUNCTION_NAME,
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=json.dumps({"mailbox": mailbox_id}).encode("utf-8"),
    )

    response_payload, logs = sync_json_lambda_invocation_successful(response)
    assert response_payload
    status_code = response_payload.get("statusCode")
    assert status_code == 204
    body = response_payload.get("body")
    assert not body

    assert logs
    assert all(log.get("Log_Level") == "INFO" for log in logs)


@pytest.mark.parametrize("mailbox_id", mailboxes)
def test_trigger_step_function_no_handshake(mailbox_id: str, sfn: SFNClient):
    wait_till_not_running(state_machine_arn=_GET_MESSAGES_SFN_ARN, sfn=sfn)

    with CloudwatchLogsCapture(log_group=_LOG_GROUP) as logs:
        execution = sfn.start_execution(
            stateMachineArn=_GET_MESSAGES_SFN_ARN,
            name=uuid4().hex,
            input=json.dumps({"mailbox": mailbox_id}),
        )

        output, result = wait_for_execution_outcome(
            execution_arn=execution["executionArn"], sfn=sfn
        )

        assert result["status"] == "SUCCEEDED"
        assert output
        assert output.get("statusCode") == 204

        logs.wait_for_logs(predicate=lambda x: x.get("logReference") == "LAMBDA0003")
        lambda_logs = logs.find_logs(parse_logs=True)
        assert lambda_logs
        assert all(log.get("Log_Level") == "INFO" for log in lambda_logs if log)
