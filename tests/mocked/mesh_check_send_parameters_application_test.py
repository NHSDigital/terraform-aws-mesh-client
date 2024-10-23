""" Testing MeshPollMailbox application """

import sys
from datetime import UTC, datetime
from http import HTTPStatus

from .mesh_testing_common import CONTEXT, was_value_logged


def test_mesh_check_send_parameters_happy_path_chunked(
    mesh_s3_bucket: str,
    environment: str,
    send_message_sfn_arn: str,
    capsys,
    mocked_lock_table,
):
    """Test the lambda as a whole, happy path for small file"""

    expected_response = {
        "statusCode": HTTPStatus.OK.value,
        "headers": {"Content-Type": "application/json"},
        "body": {
            # "internal_id": appears here in the payload but is asserted separately,
            "src_mailbox": "X26ABC2",
            "dest_mailbox": "X26ABC1",
            "workflow_id": "TESTWORKFLOW",
            "bucket": mesh_s3_bucket,
            "key": "X26ABC2/outbound/testfile.json",
            "chunked": True,
            "chunk_number": 1,
            "total_chunks": 4,
            "chunk_size": 10,
            "message_id": None,
            "current_byte_position": 0,
            "send_params": {
                "checksum": None,
                "chunked": True,
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
                "s3_bucket": mesh_s3_bucket,
                "s3_key": "X26ABC2/outbound/testfile.json",
                "sender": "X26ABC2",
                "subject": "Custom Subject",
                "total_chunks": 4,
                "workflow_id": "TESTWORKFLOW",
            },
            "lock_name": f"SendLock_{mesh_s3_bucket}_X26ABC2/outbound/testfile.json",
            "execution_id": "TEST1234",
        },
    }
    from mesh_check_send_parameters_application import (
        MeshCheckSendParametersApplication,
    )

    app = MeshCheckSendParametersApplication()
    app.config.crumb_size = 10
    app.config.chunk_size = 10
    app.config.compress_threshold = app.config.chunk_size

    response = app.main(event=sample_trigger_event(mesh_s3_bucket), context=CONTEXT)

    internal_id = response["body"]["internal_id"]
    assert len(internal_id) == 27
    internal_id_timestamp = datetime.strptime(
        internal_id[:20], "%Y%m%d%H%M%S%f"
    ).replace(tzinfo=UTC)
    assert (datetime.now(UTC) - internal_id_timestamp).total_seconds() < 10  # seconds
    del response["body"]["internal_id"]

    assert response == expected_response

    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "LAMBDA0001", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0002", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")


def test_mesh_check_send_parameters_happy_path_unchunked(
    mesh_s3_bucket: str,
    environment: str,
    send_message_sfn_arn: str,
    capsys,
    mocked_lock_table,
):
    """Test the lambda as a whole, happy path for small file"""
    from mesh_check_send_parameters_application import (
        MeshCheckSendParametersApplication,
    )

    app = MeshCheckSendParametersApplication()

    app.config.crumb_size = sys.maxsize
    app.config.chunk_size = sys.maxsize
    app.config.compress_threshold = 10

    expected_response = {
        "statusCode": HTTPStatus.OK.value,
        "headers": {"Content-Type": "application/json"},
        "body": {
            # "internal_id": appears here in the payload but is asserted separately,
            "src_mailbox": "X26ABC2",
            "dest_mailbox": "X26ABC1",
            "workflow_id": "TESTWORKFLOW",
            "bucket": mesh_s3_bucket,
            "key": "X26ABC2/outbound/testfile.json",
            "chunked": False,
            "chunk_number": 1,
            "total_chunks": 1,
            "chunk_size": sys.maxsize,
            "message_id": None,
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
                "filename": None,
                "local_id": None,
                "partner_id": None,
                "recipient": "X26ABC1",
                "s3_bucket": mesh_s3_bucket,
                "s3_key": "X26ABC2/outbound/testfile.json",
                "sender": "X26ABC2",
                "subject": "Custom Subject",
                "total_chunks": 1,
                "workflow_id": "TESTWORKFLOW",
            },
            "lock_name": f"SendLock_{mesh_s3_bucket}_X26ABC2/outbound/testfile.json",
            "execution_id": "TEST1234",
        },
    }
    response = app.main(event=sample_trigger_event(mesh_s3_bucket), context=CONTEXT)

    internal_id = response["body"]["internal_id"]
    assert len(internal_id) == 27
    internal_id_timestamp = datetime.strptime(
        internal_id[:20], "%Y%m%d%H%M%S%f"
    ).replace(tzinfo=UTC)
    assert (datetime.now(UTC) - internal_id_timestamp).total_seconds() < 10  # seconds
    del response["body"]["internal_id"]

    assert response == expected_response

    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "LAMBDA0001", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0002", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")


def sample_trigger_event(
    bucket: str, key: str = "X26ABC2/outbound/testfile.json"
) -> dict:

    s3_event = {
        "eventVersion": "1.08",
        "eventTime": "2021-06-29T14:10:55Z",
        "eventSource": "s3.amazonaws.com",
        "eventName": "PutObject",
        "awsRegion": "eu-west-2",
        "requestParameters": {
            "X-Amz-Date": "20210629T141055Z",
            "bucketName": bucket,
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "x-amz-acl": "private",
            "X-Amz-SignedHeaders": "content-md5;content-type;host;x-amz-acl;x-amz-storage-class",  # pylint: disable=line-too-long
            "Host": f"{bucket}.s3.eu-west-2.amazonaws.com",
            "X-Amz-Expires": "300",
            "key": key,
            "x-amz-storage-class": "STANDARD",
        },
        "responseElements": {
            "x-amz-server-side-encryption": "aws:kms",
            "x-amz-server-side-encryption-aws-kms-key-id": "arn:aws:kms:eu-west-2:092420156801:key/4f295c4c-17fd-4c9d-84e9-266b01de0a5a",  # noqa pylint: disable=line-too-long
        },
        "requestID": "1234567890123456",
        "eventID": "75e91cfc-f2db-4e09-8f80-a206ab4cd15e",
        "readOnly": False,
        "resources": [
            {
                "type": "AWS::S3::Object",
                "ARN": f"arn:aws:s3:::{key}",  # pylint: disable=line-too-long
            },
            {
                "accountId": "123456789012",
                "type": "AWS::S3::Bucket",
                "ARN": f"arn:aws:s3:::{bucket}",
            },
        ],
        "eventType": "AwsApiCall",
        "managementEvent": False,
        "recipientAccountId": "123456789012",
        "eventCategory": "Data",
    }

    event_bridge_event = {
        "version": "0",
        "id": "daea9bec-2d16-e943-2079-4d19b6e2ec1d",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2021-06-29T14:10:55Z",
        "region": "eu-west-2",
        "resources": [],
        "EventDetail": {
            "detail": s3_event,
        },
        "ExecutionId": "TEST1234",
    }

    return event_bridge_event
