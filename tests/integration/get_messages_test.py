import json
from collections.abc import Generator
from uuid import uuid4

import pytest
from mesh_client import MeshClient
from mypy_boto3_stepfunctions import SFNClient

from nhs_aws_helpers import lambdas


from .test_helpers import (
    CloudwatchLogsCapture,
    reset_sandbox_mailbox,
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
_SANDBOX_URL = "https://localhost:8700"


@pytest.fixture(scope="module", autouse=True)
def _clean_mailboxes():
    for mailbox_id in mailboxes:
        reset_sandbox_mailbox(mailbox_id)

@pytest.fixture(name="mesh_client_one")
def get_mesh_client_one() -> Generator[MeshClient, None, None]:
    with MeshClient(
        url=_SANDBOX_URL, mailbox=mailboxes[0], password="password", verify=False
    ) as client:
        yield client


@pytest.fixture(name="mesh_client_two")
def get_mesh_client_two() -> Generator[MeshClient, None, None]:
    with MeshClient(
        url=_SANDBOX_URL, mailbox=mailboxes[1], password="password", verify=False
    ) as client:
        yield client


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
    assert response_payload.get("statusCode") == 204
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
        assert not any(log.get("logReference") == "MESHMBOX0004" for log in lambda_logs if log)


@pytest.mark.parametrize("mailbox_id", mailboxes)
def test_trigger_step_function_handshake(mailbox_id: str, sfn: SFNClient):

    wait_till_not_running(state_machine_arn=_GET_MESSAGES_SFN_ARN, sfn=sfn)

    with CloudwatchLogsCapture(log_group=_LOG_GROUP) as logs:
        execution = sfn.start_execution(
            stateMachineArn=_GET_MESSAGES_SFN_ARN,
            name=uuid4().hex,
            input=json.dumps({"mailbox": mailbox_id, "handshake": "true"}),
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
        assert any(log.get("logReference") == "MESHMBOX0004" for log in lambda_logs if log)


def test_invoke_get_when_message_exists(mesh_client_one: MeshClient):
    recipient = mailboxes[1]
    payload = f"test: {uuid4().hex}"
    subject = uuid4().hex
    workflow_id = "WORKFLOW_1"

    sent_message_id = mesh_client_one.send_message(
        recipient=recipient,
        data=payload.encode(encoding="utf-8"),
        subject=subject,
        workflow_id=workflow_id,
    )

    response = lambdas().invoke(
        FunctionName=_FUNCTION_NAME,
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=json.dumps({"mailbox": recipient}).encode("utf-8"),
    )

    response_payload, logs = sync_json_lambda_invocation_successful(response)
    assert response_payload
    assert response_payload.get("statusCode") == 200
    body = response_payload.get("body")
    assert body
    assert body["message_count"] == 1

    assert logs
    assert all(log.get("Log_Level") == "INFO" for log in logs)

    received = body["message_list"][0]["body"]
    message_id = received["message_id"]

    assert message_id == sent_message_id
