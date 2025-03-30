import random
from http import HTTPStatus
from urllib.parse import quote_plus
from uuid import uuid4

import pytest
from mesh_client import MeshClient
from mypy_boto3_s3 import S3Client
from requests import HTTPError

from .mesh_common_test import find_log_entries
from .mesh_testing_common import (
    CONTEXT,
    KNOWN_INTERNAL_ID1,
    inject_expired_non_delivery_report,
    was_value_logged,
)


def test_mesh_fetch_file_chunk_app_no_chunks_happy_path(
    environment: str,
    mesh_s3_bucket: str,
    s3_client: S3Client,
    mesh_client_one: MeshClient,
    mesh_client_two: MeshClient,
    capsys,
):
    from mesh_fetch_message_chunk_application import MeshFetchMessageChunkApplication

    workflow_id = uuid4().hex

    app = MeshFetchMessageChunkApplication()
    content = "123456789012345678901234567890123"
    message_id = mesh_client_two.send_message(
        recipient=mesh_client_one._mailbox,
        data=content.encode(),
        workflow_id=workflow_id,
    )
    print(message_id)

    mock_input = _sample_first_input_event(
        internal_id=KNOWN_INTERNAL_ID1, message_id=message_id, release_lock=True
    )
    response = app.main(event=mock_input, context=CONTEXT)

    assert response["body"].get("internal_id") == mock_input["body"].get("internal_id")
    assert response["body"].get("internal_id") == KNOWN_INTERNAL_ID1
    # Some checks on the response body
    assert response["body"].get("complete") is True
    assert "aws_current_part_id" in response["body"]
    assert "aws_upload_id" in response["body"]

    # Should be 0 etags uploaded to S3 as multipart not used on single chunk
    assert len(response["body"].get("aws_part_etags")) == 0

    # Check we got the logs we expect
    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "MESHFETCH0001", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0001c", "Log_Level", "INFO")

    log_entry = next(find_log_entries(logs.out, "MESHFETCH0001c"))
    s3_bucket = log_entry["s3_bucket"]
    s3_key = log_entry["s3_key"]

    s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    assert s3_object
    assert s3_object["Metadata"] == {
        "mex-statuscode": "00",
        "mex-workflowid": workflow_id,
        "mex-messagetype": "DATA",
        "mex-content-compressed": "Y",
        "mex-from": mesh_client_two._mailbox,
        "mex-to": mesh_client_one._mailbox,
        "mex-messageid": message_id,
        "mex-statussuccess": "SUCCESS",
        "mex-filename": f"{message_id}.dat",
        "mex-statusdescription": "Transferred+to+recipient+mailbox",
    }

    assert was_value_logged(logs.out, "MESHFETCH0002a", "Log_Level", "INFO")
    assert not was_value_logged(logs.out, "MESHFETCH0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0011", "Log_Level", "INFO")
    assert not was_value_logged(logs.out, "MESHFETCH0010a", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")


def test_mesh_fetch_file_chunk_app_2_chunks_happy_path(
    s3_client: S3Client,
    mesh_client_one: MeshClient,
    mesh_client_two: MeshClient,
    mesh_s3_bucket: str,
    capsys,
):
    _fetch_file_chunk_app_2_chunks_(
        s3_client, mesh_client_one, mesh_client_two, capsys, 20
    )


def test_mesh_fetch_file_chunk_app_2_chunks_odd_sized_chunk_with_temp_file(
    s3_client: S3Client,
    mesh_client_one: MeshClient,
    mesh_client_two: MeshClient,
    mesh_s3_bucket: str,
    capsys,
):
    _fetch_file_chunk_app_2_chunks_(
        s3_client, mesh_client_one, mesh_client_two, capsys, 18
    )


def _fetch_file_chunk_app_2_chunks_(
    s3_client: S3Client,
    mesh_client_one: MeshClient,
    mesh_client_two: MeshClient,
    capsys,
    data_length_mb: int,
):
    """
    Test that doing chunking works
    """
    workflow_id = uuid4().hex

    mebibyte = 1024 * 1024
    # Create some test data
    data = random.randbytes(data_length_mb * mebibyte)

    message_id = mesh_client_two.send_message(
        recipient=mesh_client_one._mailbox,
        data=data,
        workflow_id=workflow_id,
    )

    mock_input = _sample_first_input_event(
        internal_id=KNOWN_INTERNAL_ID1, message_id=message_id
    )

    from mesh_fetch_message_chunk_application import MeshFetchMessageChunkApplication

    app = MeshFetchMessageChunkApplication()

    response = app.main(event=mock_input, context=CONTEXT)

    assert response["statusCode"] == HTTPStatus.PARTIAL_CONTENT.value
    assert response["body"]["chunk_num"] == 2
    assert response["body"]["complete"] is False

    # feed response into next lambda invocation
    mock_input = response

    response = app.main(event=mock_input, context=CONTEXT)

    assert response["statusCode"] == HTTPStatus.OK.value
    assert response["body"]["complete"] is True

    # Check we got the logs we expect
    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "MESHFETCH0001", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0001c", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0002", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0004", "Log_Level", "INFO")

    log_entry = next(find_log_entries(logs.out, "MESHFETCH0001c"))
    s3_bucket = log_entry["s3_bucket"]
    s3_key = log_entry["s3_key"]

    s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    assert s3_object
    assert s3_object["Metadata"] == {
        "mex-statuscode": "00",
        "mex-workflowid": workflow_id,
        "mex-messagetype": "DATA",
        "mex-content-compressed": "Y",
        "mex-from": mesh_client_two._mailbox,
        "mex-to": mesh_client_one._mailbox,
        "mex-messageid": message_id,
        "mex-statussuccess": "SUCCESS",
        "mex-filename": f"{message_id}.dat",
        "mex-statusdescription": "Transferred+to+recipient+mailbox",
    }

    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")


def test_mesh_fetch_file_chunk_app_2_chunks_using_temp_file(
    s3_client: S3Client,
    mesh_client_one: MeshClient,
    mesh_client_two: MeshClient,
    mesh_s3_bucket: str,
    capsys,
):
    """
    Test that doing chunking works with temp file
    """
    workflow_id = uuid4().hex

    mebibyte = 1024 * 1024
    # Create some test data
    data = random.randbytes(18 * mebibyte)

    message_id = mesh_client_two.send_message(
        recipient=mesh_client_one._mailbox,
        data=data,
        workflow_id=workflow_id,
    )

    mock_input = _sample_first_input_event(
        internal_id=KNOWN_INTERNAL_ID1, message_id=message_id
    )
    from mesh_fetch_message_chunk_application import MeshFetchMessageChunkApplication

    app = MeshFetchMessageChunkApplication()

    response = app.main(event=mock_input, context=CONTEXT)

    expected_return_code = HTTPStatus.PARTIAL_CONTENT.value
    assert response["statusCode"] == expected_return_code
    assert response["body"]["chunk_num"] == 2
    assert response["body"]["complete"] is False

    # feed response into next lambda invocation
    mock_input = response

    response = app.main(event=mock_input, context=CONTEXT)

    expected_return_code = HTTPStatus.OK.value
    assert response["statusCode"] == expected_return_code
    assert response["body"]["complete"] is True

    # Check we got the logs we expect
    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "MESHFETCH0001", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0001c", "Log_Level", "INFO")

    log_entry = next(find_log_entries(logs.out, "MESHFETCH0001c"))
    s3_bucket = log_entry["s3_bucket"]
    s3_key = log_entry["s3_key"]

    s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    assert s3_object
    assert s3_object["Metadata"] == {
        "mex-statuscode": "00",
        "mex-workflowid": workflow_id,
        "mex-messagetype": "DATA",
        "mex-content-compressed": "Y",
        "mex-from": mesh_client_two._mailbox,
        "mex-to": mesh_client_one._mailbox,
        "mex-messageid": message_id,
        "mex-statussuccess": "SUCCESS",
        "mex-filename": f"{message_id}.dat",
        "mex-statusdescription": "Transferred+to+recipient+mailbox",
    }

    assert was_value_logged(logs.out, "MESHFETCH0002", "Log_Level", "INFO")
    assert not was_value_logged(logs.out, "MESHFETCH0002a", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0004", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0005a", "Log_Level", "INFO")
    assert not was_value_logged(logs.out, "MESHFETCH0010a", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")


def test_mesh_fetch_file_chunk_app_report(
    s3_client: S3Client,
    mesh_client_one: MeshClient,
    mesh_client_two: MeshClient,
    mesh_s3_bucket: str,
    capsys,
):
    file_name = uuid4().hex
    subject = uuid4().hex
    local_id = uuid4().hex
    linked_message_id = uuid4().hex
    report_message_id = inject_expired_non_delivery_report(
        mailbox_id=mesh_client_one._mailbox,
        workflow_id="TESTWORKFLOW",
        file_name=file_name,
        subject=subject,
        local_id=local_id,
        linked_message_id=linked_message_id,
    )

    mock_input = _sample_first_input_event(
        internal_id=uuid4().hex, message_id=report_message_id
    )

    from mesh_fetch_message_chunk_application import MeshFetchMessageChunkApplication

    app = MeshFetchMessageChunkApplication()

    response = app.main(event=mock_input, context=CONTEXT)

    expected_return_code = HTTPStatus.OK.value
    assert response["statusCode"] == expected_return_code

    logs = capsys.readouterr()

    assert was_value_logged(logs.out, "MESHFETCH0012", "Log_Level", "INFO")

    log_entry = next(find_log_entries(logs.out, "MESHFETCH0001c"))
    s3_bucket = log_entry["s3_bucket"]
    s3_key = log_entry["s3_key"]

    s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    assert s3_object
    assert s3_object["Metadata"] == {
        "mex-to": mesh_client_one._mailbox,
        "mex-subject": quote_plus(f"NDR: {subject}"),
        "mex-workflowid": "TESTWORKFLOW",
        "mex-statussuccess": "ERROR",
        "mex-messagetype": "REPORT",
        "mex-messageid": report_message_id,
        "mex-filename": file_name,
        "mex-localid": local_id,
    }


def test_mesh_fetch_file_chunk_app_not_found_unhappy_path(
    mesh_s3_bucket,
):
    mock_input = _sample_first_input_event(
        internal_id=KNOWN_INTERNAL_ID1, message_id=uuid4().hex
    )
    from mesh_fetch_message_chunk_application import MeshFetchMessageChunkApplication

    app = MeshFetchMessageChunkApplication()

    with pytest.raises(HTTPError) as http_error:
        app.main(event=mock_input, context=CONTEXT)

    assert http_error.value.response.status_code == HTTPStatus.NOT_FOUND.value


def _sample_first_input_event(
    internal_id: str, message_id: str, release_lock: bool = False
):
    return {
        "statusCode": HTTPStatus.OK.value,
        "headers": {"Content-Type": "application/json"},
        "body": {
            "complete": False,
            "internal_id": internal_id,
            "message_id": message_id,
            "dest_mailbox": "X26ABC1",
            "release_lock": release_lock,
        },
    }
