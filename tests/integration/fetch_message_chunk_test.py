import json
import random
from urllib.parse import quote_plus
from uuid import uuid4

import pytest
from mesh_client import MeshClient
from mypy_boto3_dynamodb.service_resource import Table
from mypy_boto3_s3.service_resource import Bucket
from nhs_aws_helpers import lambdas

from integration.constants import FETCH_FUNCTION, FETCH_LOG_GROUP, LOCAL_MAILBOXES, MB
from integration.test_helpers import (
    CloudwatchLogsCapture,
    CreateReportRequest,
    put_sandbox_report,
    sync_json_lambda_invocation_successful,
)

_MAX_CHUNK_SIZE = 10 * MB


@pytest.fixture(autouse=True)
def _clear_fetch_locks(local_lock_table: Table):
    for mailbox in LOCAL_MAILBOXES:
        local_lock_table.delete_item(Key={"LockName": f"FetchLock_{mailbox}"})


def test_fetch_message_single_unchunked_message(
    mesh_client_one: MeshClient,
    local_mesh_bucket: Bucket,
):
    recipient = LOCAL_MAILBOXES[2]
    message = f"test: {uuid4().hex}".encode()
    subject = f"subject {uuid4().hex}"
    workflow_id = "WORKFLOW_1"

    sent_message_id = mesh_client_one.send_message(
        recipient=recipient,
        data=message,
        subject=subject,
        workflow_id=workflow_id,
    )

    with CloudwatchLogsCapture(log_group=FETCH_LOG_GROUP) as cw:
        response = lambdas().invoke(
            FunctionName=FETCH_FUNCTION,
            InvocationType="RequestResponse",
            LogType="Tail",
            Payload=json.dumps(
                {
                    "body": {
                        "message_id": sent_message_id,
                        "dest_mailbox": recipient,
                        "lock_name": f"FetchLock_{recipient}",
                        "execution_id": uuid4().hex,
                    }
                }
            ).encode("utf-8"),
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
    assert body["complete"]
    assert body["message_id"] == sent_message_id
    assert body["file_name"] == f"{sent_message_id}.dat"
    assert body["chunk_num"] == 1
    assert body["dest_mailbox"] == recipient
    assert body["s3_bucket"] == local_mesh_bucket.name

    s3_obj = local_mesh_bucket.Object(body["s3_key"]).get()
    assert s3_obj["Body"].read() == message
    assert s3_obj["Metadata"]["mex-messageid"] == sent_message_id
    assert s3_obj["Metadata"]["mex-from"] == mesh_client_one._mailbox
    assert s3_obj["Metadata"]["mex-to"] == recipient
    assert s3_obj["Metadata"]["mex-messagetype"] == "DATA"
    assert s3_obj["Metadata"]["mex-workflowid"] == workflow_id
    assert s3_obj["Metadata"]["mex-subject"] == quote_plus(subject)

    assert logs
    assert all(
        log.get("Log_Level") == "INFO" for log in logs if log and "Log_Level" in log
    ), logs


def test_fetch_message_report_message(
    mesh_client_one: MeshClient, local_mesh_bucket: Bucket
):
    recipient = LOCAL_MAILBOXES[2]
    subject = f"subject {uuid4().hex}"
    workflow_id = "WORKFLOW_1"
    local_id = uuid4().hex
    code = "21"

    res = put_sandbox_report(
        CreateReportRequest(
            mailbox_id=recipient,
            code=code,
            description="just testing",
            workflow_id=workflow_id,
            subject=subject,
            local_id=local_id,
        )
    )

    assert res
    sent_message_id = res["message_id"]

    with CloudwatchLogsCapture(log_group=FETCH_LOG_GROUP) as cw:
        response = lambdas().invoke(
            FunctionName=FETCH_FUNCTION,
            InvocationType="RequestResponse",
            LogType="Tail",
            Payload=json.dumps(
                {
                    "body": {
                        "message_id": sent_message_id,
                        "dest_mailbox": recipient,
                        "lock_name": f"FetchLock_{recipient}",
                        "execution_id": uuid4().hex,
                    }
                }
            ).encode("utf-8"),
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
    assert body["complete"]
    assert body["message_id"] == sent_message_id
    assert body["file_name"] == f"{sent_message_id}.ctl"
    assert body["chunk_num"] == 1
    assert body["dest_mailbox"] == recipient
    assert body["s3_bucket"] == local_mesh_bucket.name

    s3_obj = local_mesh_bucket.Object(body["s3_key"]).get()
    headers = json.loads(s3_obj["Body"].read())

    assert headers["mex-to"] == recipient
    assert headers["mex-localid"] == local_id
    assert headers["mex-messageid"] == sent_message_id
    assert headers["mex-messagetype"] == "REPORT"
    # assert headers["mex-statuscode"] == status_code
    assert headers["mex-statussuccess"] == "ERROR"
    assert headers["mex-subject"] == subject
    assert headers["mex-workflowid"] == workflow_id

    assert s3_obj["Metadata"]["mex-messageid"] == sent_message_id
    assert s3_obj["Metadata"]["mex-to"] == recipient
    assert s3_obj["Metadata"]["mex-messagetype"] == "REPORT"
    assert s3_obj["Metadata"]["mex-workflowid"] == workflow_id
    assert s3_obj["Metadata"]["mex-subject"] == quote_plus(subject)
    assert s3_obj["Metadata"]["mex-localid"] == local_id
    # assert s3_obj["Metadata"]["mex-statuscode"] == status_code
    assert s3_obj["Metadata"]["mex-statussuccess"] == "ERROR"

    assert logs
    assert all(
        log.get("Log_Level") == "INFO" for log in logs if log and "Log_Level" in log
    ), logs


def test_fetch_message_single_chunked_message_completely_reads(
    mesh_client_one: MeshClient, local_mesh_bucket: Bucket, mesh_client_two: MeshClient
):
    recipient = LOCAL_MAILBOXES[1]

    message = random.randbytes((15 * MB) - 1610)

    subject = f"subject {uuid4().hex}"
    workflow_id = "WORKFLOW_1"

    sent_message_id = mesh_client_one.send_message(
        recipient=recipient,
        data=message,
        subject=subject,
        workflow_id=workflow_id,
    )

    with CloudwatchLogsCapture(log_group=FETCH_LOG_GROUP) as cw:
        response = lambdas().invoke(
            FunctionName=FETCH_FUNCTION,
            InvocationType="RequestResponse",
            LogType="Tail",
            Payload=json.dumps(
                {
                    "body": {
                        "message_id": sent_message_id,
                        "dest_mailbox": recipient,
                        "lock_name": f"FetchLock_{recipient}",
                        "execution_id": uuid4().hex,
                        "release_lock": True,
                    }
                }
            ).encode("utf-8"),
        )

        cw.wait_for_logs(
            predicate=lambda x: x.get("logReference") in ("LAMBDA0003", "LAMBDA9999")
        )
        logs = cw.find_logs(parse_logs=True)

    payload, _ = sync_json_lambda_invocation_successful(response)
    assert payload
    assert payload.get("statusCode") == 206
    body = payload.get("body")
    assert body
    assert not body["complete"]
    assert body["message_id"] == sent_message_id
    assert body["file_name"] == f"{sent_message_id}.dat"
    assert body["chunk_num"] == 2
    assert body["dest_mailbox"] == recipient
    assert body["s3_bucket"] == local_mesh_bucket.name
    assert body["s3_key"]
    assert body["aws_upload_id"]

    assert logs
    assert all(
        log.get("Log_Level") == "INFO" for log in logs if log and "Log_Level" in log
    ), logs

    with CloudwatchLogsCapture(log_group=FETCH_LOG_GROUP) as cw:
        response = lambdas().invoke(
            FunctionName=FETCH_FUNCTION,
            InvocationType="RequestResponse",
            LogType="Tail",
            Payload=json.dumps({"body": body}).encode("utf-8"),
        )

        cw.wait_for_logs(
            predicate=lambda x: x.get("logReference") in ("LAMBDA0003", "LAMBDA9999")
        )
        logs = cw.find_logs(parse_logs=True)

    payload, _ = sync_json_lambda_invocation_successful(response)
    assert payload
    assert payload.get("statusCode") == 200
    body = payload.get("body")
    assert body
    assert body["complete"]
    assert body["message_id"] == sent_message_id
    assert body["file_name"] == f"{sent_message_id}.dat"
    assert body["chunk_num"] == 2
    assert body["dest_mailbox"] == recipient
    assert body["s3_bucket"] == local_mesh_bucket.name
    assert body["s3_key"]
    assert body["aws_upload_id"]

    s3_obj = local_mesh_bucket.Object(body["s3_key"]).get()
    assert s3_obj["Body"].read() == message
    assert s3_obj["Metadata"]["mex-messageid"] == sent_message_id
    assert s3_obj["Metadata"]["mex-from"] == mesh_client_one._mailbox
    assert s3_obj["Metadata"]["mex-to"] == recipient
    assert s3_obj["Metadata"]["mex-messagetype"] == "DATA"
    assert s3_obj["Metadata"]["mex-workflowid"] == workflow_id
    assert s3_obj["Metadata"]["mex-subject"] == quote_plus(subject)

    assert logs
    assert all(
        log.get("Log_Level") == "INFO" for log in logs if log and "Log_Level" in log
    ), logs
