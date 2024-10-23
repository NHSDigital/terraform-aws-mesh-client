import sys
from http import HTTPStatus

import pytest
from mesh_send_message_chunk_application import MaxByteExceededException

from .mesh_testing_common import (
    CONTEXT,
    FILE_CONTENT,
    KNOWN_INTERNAL_ID,
    was_value_logged,
)

FILE_SIZE = len(FILE_CONTENT)

MEBIBYTE = 1024 * 1024
DEFAULT_BUFFER_SIZE = 20 * MEBIBYTE


def test_mesh_send_file_chunk_app_no_chunks_happy_path(
    environment: str,
    mesh_s3_bucket: str,
    send_message_sfn_arn: str,
    capsys,
    mocked_lock_table,
):
    from mesh_send_message_chunk_application import MeshSendMessageChunkApplication

    app = MeshSendMessageChunkApplication()
    app.config.crumb_size = sys.maxsize
    app.config.chunk_size = sys.maxsize

    mock_lambda_input = _sample_single_chunk_input_event(mesh_s3_bucket)
    expected_lambda_response = _sample_single_chunk_input_event(mesh_s3_bucket)
    expected_lambda_response["body"].update({"complete": True})
    expected_lambda_response["body"].update(
        {"current_byte_position": len(FILE_CONTENT)}
    )
    lambda_response = app.main(event=mock_lambda_input, context=CONTEXT)

    lambda_response["body"].pop("message_id")

    assert lambda_response == expected_lambda_response
    # Check completion
    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHSEND0008", "Log_Level", "INFO")


def test_mesh_send_file_chunk_app_2_chunks_happy_path(
    environment: str,
    mesh_s3_bucket: str,
    send_message_sfn_arn: str,
    capsys,
    mocked_lock_table,
):
    from mesh_send_message_chunk_application import MeshSendMessageChunkApplication

    app = MeshSendMessageChunkApplication()
    app.config.crumb_size = 10
    app.config.chunk_size = 10
    app.config.compress_threshold = app.config.chunk_size

    mock_input = _sample_multi_chunk_input_event(mesh_s3_bucket)
    mock_response = _sample_multi_chunk_input_event(mesh_s3_bucket)
    mock_response["body"].update({"complete": True})
    mock_response["body"]["send_params"].update({"compress": True, "chunked": True})
    mock_response["body"].update({"chunk_number": 4})
    mock_response["body"].update({"current_byte_position": len(FILE_CONTENT)})
    count = 1

    while not mock_input["body"]["complete"]:
        chunk_number = mock_input["body"].get("chunk_number", 1)
        print(f">>>>>>>>>>> Chunk {chunk_number} >>>>>>>>>>>>>>>>>>>>")
        response = app.main(event=mock_input, context=CONTEXT)
        if count == 1:
            message_id = response["body"]["message_id"]
        count = count + 1
        mock_input = response
        print(response)

    response["body"].update({"current_byte_position": len(FILE_CONTENT)})

    mock_response["body"]["message_id"] = message_id

    assert response == mock_response

    # Check completion
    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHSEND0008", "Log_Level", "INFO")


def test_mesh_send_file_chunk_app_too_many_chunks(
    environment: str,
    mesh_s3_bucket: str,
    send_message_sfn_arn: str,
    capsys,
    mocked_lock_table,
):
    """Test lambda throws MaxByteExceededException when too many chunks specified"""
    from mesh_send_message_chunk_application import MeshSendMessageChunkApplication

    app = MeshSendMessageChunkApplication()

    mock_input = _sample_too_many_chunks_input_event(mesh_s3_bucket)
    mock_response = _sample_too_many_chunks_input_event(mesh_s3_bucket)
    mock_response["body"].update({"complete": True})
    mock_response["body"]["send_params"].update({"compress": True})

    with pytest.raises(MaxByteExceededException):
        app.main(event=mock_input, context=CONTEXT)


def _sample_single_chunk_input_event(bucket: str):
    """Return Example input event"""
    return {
        "statusCode": HTTPStatus.OK.value,
        "headers": {"Content-Type": "application/json"},
        "body": {
            "internal_id": KNOWN_INTERNAL_ID,
            "src_mailbox": "X26ABC2",
            "dest_mailbox": "X26ABC1",
            "workflow_id": "TESTWORKFLOW",
            "bucket": bucket,
            "key": "X26ABC2/outbound/testfile.json",
            "chunked": False,
            "chunk_number": 1,
            "total_chunks": 1,
            "complete": False,
            "current_byte_position": 0,
            "send_params": {
                "checksum": None,
                "chunked": False,
                "compress": True,
                "compressed": None,
                "content_encoding": None,
                "content_type": "binary/octet-stream",
                "encrypted": None,
                "file_size": 33,
                "filename": "testfile.json",
                "local_id": None,
                "partner_id": None,
                "recipient": "X26ABC1",
                "s3_bucket": bucket,
                "s3_key": "X26ABC2/outbound/testfile.json",
                "sender": "X26ABC2",
                "subject": "Custom Subject",
                "total_chunks": 1,
                "workflow_id": "TESTWORKFLOW",
            },
        },
    }


def _sample_multi_chunk_input_event(bucket: str):
    """Return Example input event"""
    return {
        "statusCode": HTTPStatus.OK.value,
        "headers": {"Content-Type": "application/json"},
        "body": {
            "internal_id": KNOWN_INTERNAL_ID,
            "src_mailbox": "X26ABC2",
            "dest_mailbox": "X26ABC1",
            "workflow_id": "TESTWORKFLOW",
            "bucket": bucket,
            "key": "X26ABC2/outbound/testfile.json",
            "chunked": True,
            "chunk_number": 1,
            "total_chunks": 4,
            "complete": False,
            "current_byte_position": 0,
            "execution_id": "TEST123456",
            "send_params": {
                "checksum": None,
                "chunked": True,
                "compress": True,
                "compressed": None,
                "content_encoding": None,
                "content_type": "binary/octet-stream",
                "encrypted": None,
                "file_size": 33,
                "filename": "testfile.json",
                "local_id": None,
                "partner_id": None,
                "recipient": "X26ABC1",
                "s3_bucket": bucket,
                "s3_key": "X26ABC2/outbound/testfile.json",
                "sender": "X26ABC2",
                "subject": "Custom Subject",
                "total_chunks": 4,
                "workflow_id": "TESTWORKFLOW",
            },
        },
    }


def _sample_too_many_chunks_input_event(bucket: str):
    """Return Example input event"""
    return {
        "statusCode": HTTPStatus.OK.value,
        "headers": {"Content-Type": "application/json"},
        "body": {
            "internal_id": KNOWN_INTERNAL_ID,
            "src_mailbox": "X26ABC2",
            "dest_mailbox": "X26ABC1",
            "workflow_id": "TESTWORKFLOW",
            "bucket": bucket,
            "key": "X26ABC2/outbound/testfile.json",
            "chunked": True,
            "chunk_number": 1,
            "total_chunks": 2,
            "chunk_size": 10,
            "complete": False,
            "current_byte_position": 33,
            "send_params": {
                "checksum": None,
                "chunked": True,
                "compress": True,
                "compressed": None,
                "content_encoding": None,
                "content_type": "binary/octet-stream",
                "encrypted": None,
                "file_size": 33,
                "filename": "testfile.json",
                "local_id": None,
                "partner_id": None,
                "recipient": "X26ABC1",
                "s3_bucket": bucket,
                "s3_key": "X26ABC2/outbound/testfile.json",
                "sender": "X26ABC2",
                "subject": "Custom Subject",
                "total_chunks": 2,
                "workflow_id": "TESTWORKFLOW",
            },
        },
    }


def _sample_input_event_multi_chunk(bucket: str):
    """Return Example input event"""
    return {
        "statusCode": HTTPStatus.OK.value,
        "headers": {"Content-Type": "application/json"},
        "body": {
            "internal_id": KNOWN_INTERNAL_ID,
            "src_mailbox": "X26ABC2",
            "dest_mailbox": "X26ABC1",
            "workflow_id": "TESTWORKFLOW",
            "bucket": bucket,
            "key": "X26ABC2/outbound/testfile.json",
            "chunked": True,
            "chunk_number": 1,
            "total_chunks": 3,
            "chunk_size": 14,
            "complete": False,
            "current_byte_position": 0,
            "will_compress": False,
        },
    }


def _sample_output_invoked_via_event_bridge(bucket: str):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": {
            "chunk_number": 1,
            "complete": True,
            "current_byte_position": 33,
            # "internal_id": "20210701225219765177_TESTER",
            "send_params": {
                "checksum": None,
                "chunked": False,
                "compress": True,
                "compressed": None,
                "content_encoding": None,
                "content_type": "binary/octet-stream",
                "encrypted": None,
                "file_size": 33,
                "filename": None,
                "local_id": None,
                "partner_id": None,
                "recipient": "X26ABC1",
                "s3_bucket": bucket,
                "s3_key": "X26ABC2/outbound/testfile.json",
                "sender": "X26ABC2",
                "subject": "Custom Subject",
                "total_chunks": 1,
                "workflow_id": "TESTWORKFLOW",
            },
        },
    }
