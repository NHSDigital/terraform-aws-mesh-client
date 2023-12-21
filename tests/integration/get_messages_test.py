import json
from uuid import uuid4

import pytest
from mesh_client import MeshClient
from mypy_boto3_lambda import LambdaClient
from mypy_boto3_stepfunctions import SFNClient

from .constants import (
    GET_MESSAGES_SFN_ARN,
    LOCAL_MAILBOXES,
    POLL_FUNCTION,
    POLL_LOG_GROUP,
)
from .test_helpers import (
    CloudwatchLogsCapture,
    sync_json_lambda_invocation_successful,
    wait_for_execution_outcome,
    wait_till_not_running,
)


@pytest.mark.parametrize("mailbox_id", LOCAL_MAILBOXES)
def test_invoke_get_messages_directly(mailbox_id: str, lambdas: LambdaClient):
    response = lambdas.invoke(
        FunctionName=POLL_FUNCTION,
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


@pytest.mark.parametrize("mailbox_id", LOCAL_MAILBOXES)
def test_trigger_step_function_no_handshake(mailbox_id: str, sfn: SFNClient):
    wait_till_not_running(state_machine_arn=GET_MESSAGES_SFN_ARN, sfn=sfn)

    with CloudwatchLogsCapture(log_group=POLL_LOG_GROUP) as cw:
        execution = sfn.start_execution(
            stateMachineArn=GET_MESSAGES_SFN_ARN,
            name=uuid4().hex,
            input=json.dumps({"mailbox": mailbox_id}),
        )

        output, result = wait_for_execution_outcome(
            execution_arn=execution["executionArn"], sfn=sfn
        )

        assert result["status"] == "SUCCEEDED"
        assert output
        assert output.get("statusCode") == 204

        cw.wait_for_logs(
            predicate=lambda x: x.get("logReference") in ("LAMBDA0003", "LAMBDA9999")
        )
        logs = cw.find_logs(parse_logs=True)
        assert logs
        assert all(log.get("Log_Level") == "INFO" for log in logs if log)
        assert not any(log.get("logReference") == "MESHMBOX0004" for log in logs if log)


@pytest.mark.parametrize("mailbox_id", LOCAL_MAILBOXES)
def test_trigger_step_function_handshake(mailbox_id: str, sfn: SFNClient):
    wait_till_not_running(state_machine_arn=GET_MESSAGES_SFN_ARN, sfn=sfn)

    with CloudwatchLogsCapture(log_group=POLL_LOG_GROUP) as cw:
        execution = sfn.start_execution(
            stateMachineArn=GET_MESSAGES_SFN_ARN,
            name=uuid4().hex,
            input=json.dumps({"mailbox": mailbox_id, "handshake": "true"}),
        )

        output, result = wait_for_execution_outcome(
            execution_arn=execution["executionArn"], sfn=sfn
        )

        assert result["status"] == "SUCCEEDED"
        assert output
        assert output.get("statusCode") == 204

        cw.wait_for_logs(
            predicate=lambda x: x.get("logReference") in ("LAMBDA0003", "LAMBDA9999")
        )
        logs = cw.find_logs(parse_logs=True)
        assert logs
        assert all(log.get("Log_Level") == "INFO" for log in logs if log)
        assert any(log.get("logReference") == "MESHMBOX0004" for log in logs if log)


def test_invoke_get_when_message_exists(
    mesh_client_one: MeshClient, lambdas: LambdaClient
):
    recipient = LOCAL_MAILBOXES[1]
    payload = f"test: {uuid4().hex}"
    subject = uuid4().hex
    workflow_id = "WORKFLOW_1"

    sent_message_id = mesh_client_one.send_message(
        recipient=recipient,
        data=payload.encode(encoding="utf-8"),
        subject=subject,
        workflow_id=workflow_id,
    )

    with CloudwatchLogsCapture(log_group=POLL_LOG_GROUP) as cw:
        response = lambdas.invoke(
            FunctionName=POLL_FUNCTION,
            InvocationType="RequestResponse",
            LogType="Tail",
            Payload=json.dumps({"mailbox": recipient}).encode("utf-8"),
        )

        cw.wait_for_logs(
            predicate=lambda x: x.get("logReference") in ("LAMBDA0003", "LAMBDA9999")
        )
        logs = cw.find_logs(parse_logs=True)

    response_payload, _ = sync_json_lambda_invocation_successful(response)
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
