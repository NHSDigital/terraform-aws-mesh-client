import json
from uuid import uuid4

import pytest
from mesh_client import MeshClient
from mypy_boto3_dynamodb.service_resource import Table
from mypy_boto3_lambda import LambdaClient
from mypy_boto3_stepfunctions import SFNClient

from .constants import (
    FETCH_LOG_GROUP,
    GET_MESSAGES_SFN_ARN,
    LOCAL_MAILBOXES,
    LOCK_LOG_GROUP,
    POLL_FUNCTION,
    POLL_LOG_GROUP,
)
from .test_helpers import (
    CloudwatchLogsCapture,
    sync_json_lambda_invocation_successful,
    wait_for_execution_outcome,
    wait_till_not_running,
)


@pytest.fixture(autouse=True)
def _clear_fetch_locks(local_lock_table: Table):
    for mailbox in LOCAL_MAILBOXES:
        local_lock_table.delete_item(Key={"LockName": f"FetchLock_{mailbox}"})


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

    received = body["message_list"][0]["body"]
    message_id = received["message_id"]

    assert message_id == sent_message_id


def test_trigger_step_function_get_messages_pagination(
    mesh_client_one: MeshClient, sfn: SFNClient, local_lock_table: Table
):
    wait_till_not_running(state_machine_arn=GET_MESSAGES_SFN_ARN, sfn=sfn)

    mailbox_id = mesh_client_one._mailbox
    workflow_id = "WORKFLOW_1"

    sent_message_ids = [
        mesh_client_one.send_message(
            recipient=mailbox_id,
            data=f"data {i}: {uuid4().hex}".encode(),
            subject=f"subject {i}: {uuid4().hex}",
            workflow_id=workflow_id,
        )
        for i in range(21)
    ]

    with CloudwatchLogsCapture(
        log_group=POLL_LOG_GROUP
    ) as poll_cw, CloudwatchLogsCapture(
        log_group=FETCH_LOG_GROUP
    ) as fetch_cw, CloudwatchLogsCapture(
        log_group=LOCK_LOG_GROUP
    ) as lock_cw:
        execution = sfn.start_execution(
            stateMachineArn=GET_MESSAGES_SFN_ARN,
            name=uuid4().hex,
            input=json.dumps({"mailbox": mailbox_id}),
        )

        output, result = wait_for_execution_outcome(
            execution_arn=execution["executionArn"], sfn=sfn, timeout=20
        )

        assert result["status"] == "SUCCEEDED"
        assert output
        assert output.get("statusCode") == 200

        poll_cw.wait_for_logs(
            predicate=lambda x: x.get("logReference") == "LAMBDA0003", min_results=3
        )
        fetch_cw.wait_for_logs(
            predicate=lambda x: x.get("logReference") == "LAMBDA0003",
            min_results=len(sent_message_ids),
        )
        lock_cw.wait_for_logs(
            predicate=lambda x: x.get("logReference") == "LAMBDA0003",
        )

        poll_logs = poll_cw.find_logs(parse_logs=True)
        fetch_logs = fetch_cw.find_logs(parse_logs=True)
        lock_logs = lock_cw.find_logs(parse_logs=True)

        logs = poll_logs + fetch_logs + lock_logs
        assert logs

        remove_lock_log = next(
            log for log in logs if log["logReference"] == "MESHLOCK0002"
        )
        lock_name = remove_lock_log["lock_name"]
        assert not local_lock_table.get_item(Key={"LockName": lock_name}).get("Item")

        downloaded_logs = list(
            filter(lambda x: x.get("logReference") == "MESHFETCH0011", logs)
        )

        assert len(sent_message_ids) == len(downloaded_logs)
        downloaded_message_ids = [log["message_id"] for log in downloaded_logs]

        assert set(sent_message_ids) == set(downloaded_message_ids)
