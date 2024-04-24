import random
from http import HTTPStatus

from mypy_boto3_s3 import S3Client
from pytest_httpserver import HTTPServer
from requests.exceptions import HTTPError

from .mesh_common_test import find_log_entries
from .mesh_testing_common import (
    CONTEXT,
    KNOWN_INTERNAL_ID1,
    KNOWN_MESSAGE_ID1,
    KNOWN_MESSAGE_ID2,
    was_value_logged,
)


def test_mesh_fetch_file_chunk_app_no_chunks_happy_path(
    httpserver: HTTPServer,
    environment: str,
    mesh_s3_bucket,
    s3_client,
    capsys,
):
    from mesh_fetch_message_chunk_application import MeshFetchMessageChunkApplication

    app = MeshFetchMessageChunkApplication()

    """Test the lambda with small file, no chunking, happy path"""
    # Mock responses from MESH server
    content = "123456789012345678901234567890123"

    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}",
        method="GET",
    ).respond_with_data(
        content,
        status=HTTPStatus.OK.value,
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(content)),
            "Connection": "keep-alive",
            "Mex-Messageid": KNOWN_MESSAGE_ID1,
            "Mex-From": "MESH-TEST2",
            "Mex-To": "MESH-TEST1",
            "Mex-Fromsmtp": "mesh.automation.testclient2@nhs.org",
            "Mex-Tosmtp": "mesh.automation.testclient1@nhs.org",
            "Mex-Filename": "testfile.txt",
            "Mex-Workflowid": "TESTWORKFLOW",
            "Mex-Messagetype": "DATA",
            "Mex-Version": "1.0",
            "Mex-Addresstype": "ALL",
            "Mex-Statuscode": "00",
            "Mex-Statusevent": "TRANSFER",
            "Mex-Statusdescription": "Transferred to recipient mailbox",
            "Mex-Statussuccess": "SUCCESS",
            "Mex-Statustimestamp": "20210705162157",
            "Mex-Content-Compressed": "N",
            "Etag": "915cd12d58ce2f820959e9ba41b2ebb02f2e6005",
        },
    )

    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}/status/acknowledged",
        method="PUT",
    ).respond_with_data(
        status=HTTPStatus.OK.value,
    )

    mock_input = _sample_first_input_event()
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
    assert s3_object["Metadata"]["mex-messageid"] == KNOWN_MESSAGE_ID1
    assert s3_object["Metadata"]["mex-messagetype"] == "DATA"
    assert s3_object["Metadata"]["mex-to"] == "MESH-TEST1"
    assert s3_object["Metadata"]["mex-from"] == "MESH-TEST2"
    assert s3_object["Metadata"]["mex-workflowid"] == "TESTWORKFLOW"
    assert was_value_logged(logs.out, "MESHFETCH0002a", "Log_Level", "INFO")
    assert not was_value_logged(logs.out, "MESHFETCH0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0011", "Log_Level", "INFO")
    # self.assertTrue(
    #     was_value_logged(logs.out, "MESHFETCH0005a", "Log_Level", "INFO")
    # )
    # self.assertFalse(
    #     was_value_logged(logs.out, "MESHFETCH0008", "Log_Level", "INFO")
    # )
    assert not was_value_logged(logs.out, "MESHFETCH0010a", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")


def test_mesh_fetch_file_chunk_app_2_chunks_happy_path(
    httpserver: HTTPServer, s3_client: S3Client, mesh_s3_bucket: str, capsys
):
    _fetch_file_chunk_app_2_chunks_(httpserver, s3_client, capsys, 20)


def test_mesh_fetch_file_chunk_app_2_chunks_odd_sized_chunk_with_temp_file(
    httpserver: HTTPServer, s3_client: S3Client, mesh_s3_bucket: str, capsys
):
    _fetch_file_chunk_app_2_chunks_(httpserver, s3_client, capsys, 18)


def _fetch_file_chunk_app_2_chunks_(
    httpserver: HTTPServer,
    s3_client: S3Client,
    capsys,
    data_length: int,
):
    """
    Test that doing chunking works
    """
    mebibyte = 1024 * 1024
    # Create some test data
    data1_length = data_length * mebibyte  # 20 MiB
    data1 = random.randbytes(data1_length)
    data2_length = 4 * mebibyte  # 4 MiB
    data2 = random.randbytes(data2_length)

    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}",
        method="GET",
    ).respond_with_data(
        data1,
        status=HTTPStatus.PARTIAL_CONTENT.value,
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(data1_length),
            "Connection": "keep-alive",
            "Mex-Chunk-Range": "1:2",
            "Mex-Total-Chunks": "2",
            "Mex-Messageid": KNOWN_MESSAGE_ID1,
            "Mex-From": "MESH-TEST2",
            "Mex-To": "MESH-TEST1",
            "Mex-Fromsmtp": "mesh.automation.testclient2@nhs.org",
            "Mex-Tosmtp": "mesh.automation.testclient1@nhs.org",
            "Mex-Filename": "testfile.txt",
            "Mex-Workflowid": "TESTWORKFLOW",
            "Mex-Messagetype": "DATA",
            "Mex-Version": "1.0",
            "Mex-Addresstype": "ALL",
            "Mex-Statuscode": "00",
            "Mex-Statusevent": "TRANSFER",
            "Mex-Statusdescription": "Transferred to recipient mailbox",
            "Mex-Statussuccess": "SUCCESS",
            "Mex-Statustimestamp": "20210705162157",
            "Mex-Content-Compressed": "N",
            "Etag": "915cd12d58ce2f820959e9ba41b2ebb02f2e6005",
        },
    )
    # next chunk http response
    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}/2",
        method="GET",
    ).respond_with_data(
        data2,
        status=HTTPStatus.OK.value,
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(data2_length),
            "Mex-Chunk-Range": "2:2",
            "Mex-Total-Chunks": "2",
            "Connection": "keep-alive",
            "Mex-Messageid": KNOWN_MESSAGE_ID1,
            "Mex-From": "MESH-TEST2",
            "Mex-To": "MESH-TEST1",
            "Mex-Fromsmtp": "mesh.automation.testclient2@nhs.org",
            "Mex-Tosmtp": "mesh.automation.testclient1@nhs.org",
            "Mex-Filename": "testfile.txt",
            "Mex-Workflowid": "TESTWORKFLOW",
            "Mex-Messagetype": "DATA",
            "Mex-Version": "1.0",
            "Mex-Addresstype": "ALL",
            "Mex-Statuscode": "00",
            "Mex-Statusevent": "TRANSFER",
            "Mex-Statusdescription": "Transferred to recipient mailbox",
            "Mex-Statussuccess": "SUCCESS",
            "Mex-Statustimestamp": "20210705162157",
            "Mex-Content-Compressed": "N",
            "Etag": "915cd12d58ce2f820959e9ba41b2ebb02f2e6005",
        },
    )
    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}/status/acknowledged",
        method="PUT",
    ).respond_with_data(
        status=HTTPStatus.OK.value,
    )

    mock_input = _sample_first_input_event()

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
    assert was_value_logged(logs.out, "MESHFETCH0002", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0004", "Log_Level", "INFO")

    log_entry = next(find_log_entries(logs.out, "MESHFETCH0001c"))
    s3_bucket = log_entry["s3_bucket"]
    s3_key = log_entry["s3_key"]

    s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    assert s3_object
    assert s3_object["Metadata"]["mex-messageid"] == KNOWN_MESSAGE_ID1
    assert s3_object["Metadata"]["mex-messagetype"] == "DATA"
    assert s3_object["Metadata"]["mex-to"] == "MESH-TEST1"
    assert s3_object["Metadata"]["mex-from"] == "MESH-TEST2"
    assert s3_object["Metadata"]["mex-workflowid"] == "TESTWORKFLOW"

    # self.assertTrue(
    #     was_value_logged("MESHFETCH0005a", "Log_Level", "INFO")
    # )
    # self.assertFalse(
    #     was_value_logged("MESHFETCH0008", "Log_Level", "INFO")
    # )
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")


def test_mesh_fetch_file_chunk_app_2_chunks_using_temp_file(
    httpserver: HTTPServer, s3_client: S3Client, mesh_s3_bucket: str, capsys
):
    """
    Test that doing chunking works with temp file
    """
    mebibyte = 1024 * 1024
    # Create some test data
    data1_length = 18 * mebibyte  # 20 MiB
    data1 = random.randbytes(data1_length)
    data2_length = 4 * mebibyte  # 4 MiB
    data2 = random.randbytes(data2_length)

    # Mock responses from MESH server TODO refactor!
    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}",
        method="GET",
    ).respond_with_data(
        data1,
        status=HTTPStatus.PARTIAL_CONTENT.value,
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(data1_length),
            "Connection": "keep-alive",
            "Mex-Chunk-Range": "1:2",
            "Mex-Total-Chunks": "2",
            "Mex-Messageid": KNOWN_MESSAGE_ID1,
            "Mex-From": "MESH-TEST2",
            "Mex-To": "MESH-TEST1",
            "Mex-Fromsmtp": "mesh.automation.testclient2@nhs.org",
            "Mex-Tosmtp": "mesh.automation.testclient1@nhs.org",
            "Mex-Filename": "testfile.txt",
            "Mex-Workflowid": "TESTWORKFLOW",
            "Mex-Messagetype": "DATA",
            "Mex-Version": "1.0",
            "Mex-Addresstype": "ALL",
            "Mex-Statuscode": "00",
            "Mex-Statusevent": "TRANSFER",
            "Mex-Statusdescription": "Transferred to recipient mailbox",
            "Mex-Statussuccess": "SUCCESS",
            "Mex-Statustimestamp": "20210705162157",
            "Mex-Content-Compressed": "N",
            "Etag": "915cd12d58ce2f820959e9ba41b2ebb02f2e6005",
        },
    )
    # next chunk http response
    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}/2",
        method="GET",
    ).respond_with_data(
        data2,
        status=HTTPStatus.OK.value,
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(data2_length),
            "Mex-Chunk-Range": "2:2",
            "Mex-Total-Chunks": "2",
            "Connection": "keep-alive",
            "Mex-Messageid": KNOWN_MESSAGE_ID1,
            "Mex-From": "MESH-TEST2",
            "Mex-To": "MESH-TEST1",
            "Mex-Fromsmtp": "mesh.automation.testclient2@nhs.org",
            "Mex-Tosmtp": "mesh.automation.testclient1@nhs.org",
            "Mex-Filename": "testfile.txt",
            "Mex-Workflowid": "TESTWORKFLOW",
            "Mex-Messagetype": "DATA",
            "Mex-Version": "1.0",
            "Mex-Addresstype": "ALL",
            "Mex-Statuscode": "00",
            "Mex-Statusevent": "TRANSFER",
            "Mex-Statusdescription": "Transferred to recipient mailbox",
            "Mex-Statussuccess": "SUCCESS",
            "Mex-Statustimestamp": "20210705162157",
            "Mex-Content-Compressed": "N",
            "Etag": "915cd12d58ce2f820959e9ba41b2ebb02f2e6005",
        },
    )
    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}/status/acknowledged",
        method="PUT",
    ).respond_with_data(
        status=HTTPStatus.OK.value,
    )

    mock_input = _sample_first_input_event()
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
    assert s3_object["Metadata"]["mex-messagetype"] == "DATA"
    assert s3_object["Metadata"]["mex-to"] == "MESH-TEST1"
    assert s3_object["Metadata"]["mex-from"] == "MESH-TEST2"
    assert s3_object["Metadata"]["mex-workflowid"] == "TESTWORKFLOW"

    assert was_value_logged(logs.out, "MESHFETCH0002", "Log_Level", "INFO")
    assert not was_value_logged(logs.out, "MESHFETCH0002a", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0004", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHFETCH0005a", "Log_Level", "INFO")
    assert not was_value_logged(logs.out, "MESHFETCH0010a", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")


def test_mesh_fetch_file_chunk_app_report(
    httpserver: HTTPServer, s3_client: S3Client, mesh_s3_bucket: str, capsys
):
    """Test the lambda with a Non-Delivery Report"""
    # Mock responses from MESH server
    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}",
        method="GET",
    ).respond_with_data(
        status=HTTPStatus.OK.value,
        headers={
            "Content-Type": "application/octet-stream",
            "Connection": "keep-alive",
            "Mex-Messageid": KNOWN_MESSAGE_ID2,
            "Mex-Linkedmsgid": KNOWN_MESSAGE_ID1,
            "Mex-To": "MESH-TEST1",
            "Mex-Subject": "NDR",
            "Mex-Workflowid": "TESTWORKFLOW",
            "Mex-Messagetype": "REPORT",
            "Mex-Version": "1.0",
            "Mex-Addresstype": "ALL",
            "Mex-Statuscode": "14",
            "Mex-Statusevent": "SEND",
            "Mex-Statusdescription": "Message not collected by recipient after 5 days",  # pylint: disable=line-too-long
            "Mex-Statussuccess": "ERROR",
            "Mex-Statustimestamp": "20210705162157",
            "Mex-Content-Compressed": "N",
            "Etag": "915cd12d58ce2f820959e9ba41b2ebb02f2e6005",
            "Strict-Transport-Security": "max-age=15552000",
        },
    )
    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}/status/acknowledged",
        method="PUT",
    ).respond_with_data(
        status=HTTPStatus.OK.value,
    )
    mock_input = _sample_first_input_event()

    from mesh_fetch_message_chunk_application import MeshFetchMessageChunkApplication

    app = MeshFetchMessageChunkApplication()

    response = app.main(event=mock_input, context=CONTEXT)

    expected_return_code = HTTPStatus.OK.value
    assert response["statusCode"] == expected_return_code

    logs = capsys.readouterr()
    # self.assertTrue(
    #     was_value_logged(logs.out, "MESHFETCH0008", "Log_Level", "INFO")
    # )
    assert was_value_logged(logs.out, "MESHFETCH0012", "Log_Level", "INFO")

    log_entry = next(find_log_entries(logs.out, "MESHFETCH0001c"))
    s3_bucket = log_entry["s3_bucket"]
    s3_key = log_entry["s3_key"]

    s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    assert s3_object
    assert s3_object["Metadata"]["mex-messagetype"] == "REPORT"
    assert s3_object["Metadata"]["mex-to"] == "MESH-TEST1"
    assert s3_object["Metadata"]["mex-workflowid"] == "TESTWORKFLOW"
    assert s3_object["Metadata"]["mex-statussuccess"] == "ERROR"


def test_mesh_fetch_file_chunk_app_gone_away_unhappy_path(
    httpserver: HTTPServer,
    mesh_s3_bucket,
):
    """Test the lambda with unhappy path"""
    httpserver.expect_request(
        f"/messageexchange/MESH-TEST1/inbox/{KNOWN_MESSAGE_ID1}",
        method="GET",
    ).respond_with_data(
        status=HTTPStatus.OK.value,
        headers={
            "Content-Type": "application/json",
        },
    )

    mock_input = _sample_first_input_event()
    try:
        from mesh_fetch_message_chunk_application import (
            MeshFetchMessageChunkApplication,
        )

        app = MeshFetchMessageChunkApplication()

        app.main(event=mock_input, context=CONTEXT)
    except HTTPError:
        return
    raise AssertionError("Failed to raise 410 Client Error")


def _sample_first_input_event():
    return {
        "statusCode": HTTPStatus.OK.value,
        "headers": {"Content-Type": "application/json"},
        "body": {
            "complete": False,
            "internal_id": KNOWN_INTERNAL_ID1,
            "message_id": KNOWN_MESSAGE_ID1,
            "dest_mailbox": "MESH-TEST1",
        },
    }
