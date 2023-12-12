import json
import random
from typing import Generator
from urllib.parse import quote_plus
from uuid import uuid4

import pytest
from mypy_boto3_s3.service_resource import Bucket
from integration.test_helpers import reset_sandbox_mailbox, sync_json_lambda_invocation_successful, put_sandbox_report, \
    CreateReportRequest
from mesh_client import MeshClient
from nhs_aws_helpers import lambdas


_MB = 1024 * 1024

_MAX_CHUNK_SIZE = 10 * _MB

mailboxes = ["X26ABC1", "X26ABC2", "X26ABC3"]


_FUNCTION_NAME = "local-mesh-fetch-message-chunk"
_LOG_GROUP = f"/aws/lambda/{_FUNCTION_NAME}"
_SANDBOX_URL = "https://localhost:8700"


@pytest.fixture(scope="module", autouse=True)
def _clean_mailboxes():
    for mailbox_id in mailboxes:
        reset_sandbox_mailbox(mailbox_id)

@pytest.fixture(name="mesh_client_one")
def get_mesh_client_one() -> Generator[MeshClient, None, None]:
    with MeshClient(
        url=_SANDBOX_URL, mailbox=mailboxes[0], password="password", verify=False, max_chunk_size=10 * _MB
    ) as client:
        yield client


@pytest.fixture(name="mesh_client_two")
def get_mesh_client_two() -> Generator[MeshClient, None, None]:
    with MeshClient(
        url=_SANDBOX_URL, mailbox=mailboxes[1], password="password", verify=False
    ) as client:
        yield client


def test_fetch_message_single_unchunked_message(mesh_client_one: MeshClient, local_mesh_bucket: Bucket):

    recipient = mailboxes[2]
    message = f"test: {uuid4().hex}".encode()
    subject = f"subject {uuid4().hex}"
    workflow_id = "WORKFLOW_1"

    sent_message_id = mesh_client_one.send_message(
        recipient=recipient,
        data=message,
        subject=subject,
        workflow_id=workflow_id,
    )

    response = lambdas().invoke(
        FunctionName=_FUNCTION_NAME,
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=json.dumps({"body": {"message_id": sent_message_id, "dest_mailbox": recipient}}).encode("utf-8"),
    )

    response_payload, logs = sync_json_lambda_invocation_successful(response)
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
    assert s3_obj["Metadata"]["mex-from"] == mesh_client_one._mailbox
    assert s3_obj["Metadata"]["mex-to"] == recipient
    assert s3_obj["Metadata"]["mex-messagetype"] == "DATA"
    assert s3_obj["Metadata"]["mex-workflowid"] == workflow_id
    assert s3_obj["Metadata"]["mex-subject"] == quote_plus(subject)

    assert logs
    assert all(log.get("Log_Level") == "INFO" for log in logs)



def test_fetch_message_report_message(mesh_client_one: MeshClient, local_mesh_bucket: Bucket):

    recipient = mailboxes[2]
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
            local_id=local_id
        )
    )

    assert res
    sent_message_id = res["message_id"]

    response = lambdas().invoke(
        FunctionName=_FUNCTION_NAME,
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=json.dumps({"body": {"message_id": sent_message_id, "dest_mailbox": recipient}}).encode("utf-8"),
    )

    response_payload, logs = sync_json_lambda_invocation_successful(response)
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
    headers = json.loads(s3_obj["Body"].read())

    assert headers["mex-to"] == recipient
    assert headers["mex-localid"] == local_id
    assert headers["mex-messageid"] == sent_message_id
    assert headers["mex-messagetype"] == "REPORT"
    # assert headers["mex-statuscode"] == status_code
    assert headers["mex-statussuccess"] == "ERROR"
    assert headers["mex-subject"] == subject
    assert headers["mex-workflowid"] == workflow_id


    assert s3_obj["Metadata"]["mex-to"] == recipient
    assert s3_obj["Metadata"]["mex-messagetype"] == "REPORT"
    assert s3_obj["Metadata"]["mex-workflowid"] == workflow_id
    assert s3_obj["Metadata"]["mex-subject"] == quote_plus(subject)
    assert s3_obj["Metadata"]["mex-localid"] == local_id
    # assert s3_obj["Metadata"]["mex-statuscode"] == status_code
    assert s3_obj["Metadata"]["mex-statussuccess"] == "ERROR"

    assert logs
    assert all(log.get("Log_Level") == "INFO" for log in logs)



def test_fetch_message_single_chunked_message(mesh_client_one: MeshClient, local_mesh_bucket: Bucket, mesh_client_two: MeshClient):

    recipient = mailboxes[1]

    message = random.randbytes(15 * _MB)

    subject = f"subject {uuid4().hex}"
    workflow_id = "WORKFLOW_1"

    sent_message_id = mesh_client_one.send_message(
        recipient=recipient,
        data=message,
        subject=subject,
        workflow_id=workflow_id,
    )

    resp = mesh_client_two.retrieve_message_chunk(sent_message_id, 1)
    resp.raise_for_status()
    resp.raw.decode_content = True
    crumbs = list(resp.iter_content(chunk_size=5*_MB))
    assert crumbs


    response = lambdas().invoke(
        FunctionName=_FUNCTION_NAME,
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=json.dumps({"body": {"message_id": sent_message_id, "dest_mailbox": recipient}}).encode("utf-8"),
    )

    response_payload, logs = sync_json_lambda_invocation_successful(response)
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
    assert s3_obj["Metadata"]["mex-from"] == mesh_client_one._mailbox
    assert s3_obj["Metadata"]["mex-to"] == recipient
    assert s3_obj["Metadata"]["mex-messagetype"] == "DATA"
    assert s3_obj["Metadata"]["mex-workflowid"] == workflow_id
    assert s3_obj["Metadata"]["mex-subject"] == quote_plus(subject)

    assert logs
    assert all(log.get("Log_Level") == "INFO" for log in logs)
