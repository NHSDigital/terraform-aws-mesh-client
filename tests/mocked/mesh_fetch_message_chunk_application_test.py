""" Testing MeshFetchMessageChunk Application """
import json
import random
from http import HTTPStatus
from unittest import mock

import boto3
import requests_mock
from mesh_fetch_message_chunk_application import (
    MeshFetchMessageChunkApplication,
)
from moto import mock_s3, mock_secretsmanager, mock_ssm, mock_stepfunctions
from requests.exceptions import HTTPError

from .mesh_common_test import find_log_entries
from .mesh_testing_common import (
    MeshTestCase,
    MeshTestingCommon,
)


@mock_secretsmanager
@mock_ssm
@mock_s3
@mock_stepfunctions
class TestMeshFetchMessageChunkApplication(MeshTestCase):
    """Testing MeshFetchMessageChunk application"""

    @mock.patch.dict("os.environ", MeshTestingCommon.os_environ_values)
    def setUp(self):
        """Override setup to use correct application object"""
        super().setUp()
        self.app = MeshFetchMessageChunkApplication()
        self.environment = self.app.system_config["ENVIRONMENT"]

    @mock.patch.object(MeshFetchMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_fetch_file_chunk_app_no_chunks_happy_path(
        self, mock_create_new_internal_id, response_mocker
    ):
        """Test the lambda with small file, no chunking, happy path"""
        # Mock responses from MESH server
        content = "123456789012345678901234567890123"

        response_mocker.get(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}",
            text=content,
            status_code=HTTPStatus.OK.value,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(content)),
                "Connection": "keep-alive",
                "Mex-Messageid": MeshTestingCommon.KNOWN_MESSAGE_ID1,
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
        response_mocker.put(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}/status/acknowledged",
        )

        mock_create_new_internal_id.return_value = MeshTestingCommon.KNOWN_INTERNAL_ID1
        s3_client = boto3.client("s3", region_name="eu-west-2")
        ssm_client = boto3.client("ssm", region_name="eu-west-2")
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        mock_input = self._sample_first_input_event()
        assert self.app
        try:
            response = self.app.main(
                event=mock_input, context=MeshTestingCommon.CONTEXT
            )
        except Exception as exception:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {exception!s}")

        # print(response)

        assert response["body"].get("internal_id") == mock_input["body"].get(
            "internal_id"
        )
        assert (
            response["body"].get("internal_id") == MeshTestingCommon.KNOWN_INTERNAL_ID1
        )
        # Some checks on the response body
        assert response["body"].get("complete") is True
        assert "aws_current_part_id" in response["body"]
        assert "aws_upload_id" in response["body"]

        # Should be 0 etags uploaded to S3 as multipart not used on single chunk
        assert len(response["body"].get("aws_part_etags")) == 0

        # Check we got the logs we expect
        assert self.log_helper.was_value_logged("MESHFETCH0001", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHFETCH0001c", "Log_Level", "INFO")

        log_entry = next(find_log_entries(self.log_helper, "MESHFETCH0001c"))
        s3_bucket = log_entry["s3_bucket"]
        s3_key = log_entry["s3_key"]

        s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        assert s3_object
        assert (
            s3_object["Metadata"]["mex-messageid"]
            == MeshTestingCommon.KNOWN_MESSAGE_ID1
        )
        assert s3_object["Metadata"]["mex-messagetype"] == "DATA"
        assert s3_object["Metadata"]["mex-to"] == "MESH-TEST1"
        assert s3_object["Metadata"]["mex-from"] == "MESH-TEST2"
        assert s3_object["Metadata"]["mex-workflowid"] == "TESTWORKFLOW"
        assert self.log_helper.was_value_logged("MESHFETCH0002a", "Log_Level", "INFO")
        assert not self.log_helper.was_value_logged(
            "MESHFETCH0003", "Log_Level", "INFO"
        )
        assert self.log_helper.was_value_logged("MESHFETCH0011", "Log_Level", "INFO")
        # self.assertTrue(
        #     self.log_helper.was_value_logged("MESHFETCH0005a", "Log_Level", "INFO")
        # )
        # self.assertFalse(
        #     self.log_helper.was_value_logged("MESHFETCH0008", "Log_Level", "INFO")
        # )
        assert not self.log_helper.was_value_logged(
            "MESHFETCH0010a", "Log_Level", "INFO"
        )
        assert self.log_helper.was_value_logged("LAMBDA0003", "Log_Level", "INFO")

    @mock.patch.object(MeshFetchMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_fetch_file_chunk_app_2_chunks_happy_path(
        self,
        mock_create_new_internal_id,
        mock_response,
    ):
        self._fetch_file_chunk_app_2_chunks_(
            20, mock_create_new_internal_id, mock_response
        )

    @mock.patch.object(MeshFetchMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_fetch_file_chunk_app_2_chunks_odd_sized_chunk_with_temp_file(
        self,
        mock_create_new_internal_id,
        mock_response,
    ):
        self._fetch_file_chunk_app_2_chunks_(
            18, mock_create_new_internal_id, mock_response
        )

    def _fetch_file_chunk_app_2_chunks_(
        self,
        data_length,
        mock_create_new_internal_id,
        mock_response,
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

        mock_response.get(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}",
            content=data1,
            status_code=HTTPStatus.PARTIAL_CONTENT.value,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(data1_length),
                "Connection": "keep-alive",
                "Mex-Chunk-Range": "1:2",
                "Mex-Total-Chunks": "2",
                "Mex-Messageid": MeshTestingCommon.KNOWN_MESSAGE_ID1,
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
        mock_response.get(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}/2",
            content=data2,
            status_code=HTTPStatus.OK.value,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(data2_length),
                "Mex-Chunk-Range": "2:2",
                "Mex-Total-Chunks": "2",
                "Connection": "keep-alive",
                "Mex-Messageid": MeshTestingCommon.KNOWN_MESSAGE_ID1,
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
        mock_response.put(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}/status/acknowledged",
            text=json.dumps({"messageId": MeshTestingCommon.KNOWN_MESSAGE_ID1}),
            headers={
                "Content-Type": "application/json",
                "Transfer-Encoding": "chunked",
                "Connection": "keep-alive",
            },
        )

        mock_create_new_internal_id.return_value = MeshTestingCommon.KNOWN_INTERNAL_ID1

        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        mock_input = self._sample_first_input_event()
        assert self.app
        try:
            response = self.app.main(
                event=mock_input, context=MeshTestingCommon.CONTEXT
            )
        except Exception as exception:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {exception!s}")

        expected_return_code = HTTPStatus.PARTIAL_CONTENT.value
        assert response["statusCode"] == expected_return_code
        assert response["body"]["chunk_num"] == 2
        assert response["body"]["complete"] is False

        # feed response into next lambda invocation
        mock_input = response

        try:
            response = self.app.main(
                event=mock_input, context=MeshTestingCommon.CONTEXT
            )
        except Exception as exception:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {exception!s}")

        expected_return_code = HTTPStatus.OK.value
        assert response["statusCode"] == expected_return_code
        assert response["body"]["complete"] is True

        # Check we got the logs we expect
        assert self.log_helper.was_value_logged("MESHFETCH0001", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHFETCH0001c", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHFETCH0002", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHFETCH0003", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHFETCH0004", "Log_Level", "INFO")

        log_entry = next(find_log_entries(self.log_helper, "MESHFETCH0001c"))
        s3_bucket = log_entry["s3_bucket"]
        s3_key = log_entry["s3_key"]

        s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        assert s3_object
        assert (
            s3_object["Metadata"]["mex-messageid"]
            == MeshTestingCommon.KNOWN_MESSAGE_ID1
        )
        assert s3_object["Metadata"]["mex-messagetype"] == "DATA"
        assert s3_object["Metadata"]["mex-to"] == "MESH-TEST1"
        assert s3_object["Metadata"]["mex-from"] == "MESH-TEST2"
        assert s3_object["Metadata"]["mex-workflowid"] == "TESTWORKFLOW"

        # self.assertTrue(
        #     self.log_helper.was_value_logged("MESHFETCH0005a", "Log_Level", "INFO")
        # )
        # self.assertFalse(
        #     self.log_helper.was_value_logged("MESHFETCH0008", "Log_Level", "INFO")
        # )
        assert self.log_helper.was_value_logged("LAMBDA0003", "Log_Level", "INFO")

    @mock.patch.object(MeshFetchMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_fetch_file_chunk_app_2_chunks_using_temp_file(
        self, mock_create_new_internal_id, mock_response
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
        mock_response.get(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}",
            content=data1,
            status_code=HTTPStatus.PARTIAL_CONTENT.value,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(data1_length),
                "Connection": "keep-alive",
                "Mex-Chunk-Range": "1:2",
                "Mex-Total-Chunks": "2",
                "Mex-Messageid": MeshTestingCommon.KNOWN_MESSAGE_ID1,
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
        mock_response.get(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}/2",
            content=data2,
            status_code=HTTPStatus.OK.value,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(data2_length),
                "Mex-Chunk-Range": "2:2",
                "Mex-Total-Chunks": "2",
                "Connection": "keep-alive",
                "Mex-Messageid": MeshTestingCommon.KNOWN_MESSAGE_ID1,
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
        mock_response.put(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}/status/acknowledged",
            text=json.dumps({"messageId": MeshTestingCommon.KNOWN_MESSAGE_ID1}),
            headers={
                "Content-Type": "application/json",
                "Transfer-Encoding": "chunked",
                "Connection": "keep-alive",
            },
        )

        mock_create_new_internal_id.return_value = MeshTestingCommon.KNOWN_INTERNAL_ID1

        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        mock_input = self._sample_first_input_event()
        assert self.app
        try:
            response = self.app.main(
                event=mock_input, context=MeshTestingCommon.CONTEXT
            )
        except Exception as exception:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {exception!s}")

        expected_return_code = HTTPStatus.PARTIAL_CONTENT.value
        assert response["statusCode"] == expected_return_code
        assert response["body"]["chunk_num"] == 2
        assert response["body"]["complete"] is False

        # feed response into next lambda invocation
        mock_input = response

        try:
            response = self.app.main(
                event=mock_input, context=MeshTestingCommon.CONTEXT
            )
        except Exception as exception:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {exception!s}")

        expected_return_code = HTTPStatus.OK.value
        assert response["statusCode"] == expected_return_code
        assert response["body"]["complete"] is True

        # Check we got the logs we expect
        assert self.log_helper.was_value_logged("MESHFETCH0001", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHFETCH0001c", "Log_Level", "INFO")

        log_entry = next(find_log_entries(self.log_helper, "MESHFETCH0001c"))
        s3_bucket = log_entry["s3_bucket"]
        s3_key = log_entry["s3_key"]

        s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        assert s3_object
        assert s3_object["Metadata"]["mex-messagetype"] == "DATA"
        assert s3_object["Metadata"]["mex-to"] == "MESH-TEST1"
        assert s3_object["Metadata"]["mex-from"] == "MESH-TEST2"
        assert s3_object["Metadata"]["mex-workflowid"] == "TESTWORKFLOW"

        assert self.log_helper.was_value_logged("MESHFETCH0002", "Log_Level", "INFO")
        assert not self.log_helper.was_value_logged(
            "MESHFETCH0002a", "Log_Level", "INFO"
        )
        assert self.log_helper.was_value_logged("MESHFETCH0003", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHFETCH0004", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHFETCH0005a", "Log_Level", "INFO")
        assert not self.log_helper.was_value_logged(
            "MESHFETCH0010a", "Log_Level", "INFO"
        )
        assert self.log_helper.was_value_logged("LAMBDA0003", "Log_Level", "INFO")

    @mock.patch.object(MeshFetchMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_fetch_file_chunk_app_report(
        self, mock_create_new_internal_id, response_mocker
    ):
        """Test the lambda with a Non-Delivery Report"""
        # Mock responses from MESH server
        response_mocker.get(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}",
            text="",
            status_code=HTTPStatus.OK.value,
            headers={
                "Content-Type": "application/octet-stream",
                "Connection": "keep-alive",
                "Mex-Messageid": MeshTestingCommon.KNOWN_MESSAGE_ID2,
                "Mex-Linkedmsgid": MeshTestingCommon.KNOWN_MESSAGE_ID1,
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
        response_mocker.put(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}/status/acknowledged",
            text=json.dumps({"messageId": MeshTestingCommon.KNOWN_MESSAGE_ID1}),
            headers={
                "Content-Type": "application/json",
                "Transfer-Encoding": "chunked",
                "Connection": "keep-alive",
            },
        )
        mock_create_new_internal_id.return_value = MeshTestingCommon.KNOWN_INTERNAL_ID1
        s3_client = boto3.client("s3", region_name="eu-west-2")
        ssm_client = boto3.client("ssm", region_name="eu-west-2")
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        mock_input = self._sample_first_input_event()
        assert self.app
        try:
            response = self.app.main(
                event=mock_input, context=MeshTestingCommon.CONTEXT
            )
        except Exception as exception:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {exception!s}")

        expected_return_code = HTTPStatus.OK.value
        assert response["statusCode"] == expected_return_code
        # self.assertTrue(
        #     self.log_helper.was_value_logged("MESHFETCH0008", "Log_Level", "INFO")
        # )

        assert self.log_helper.was_value_logged("MESHFETCH0012", "Log_Level", "INFO")

        log_entry = next(find_log_entries(self.log_helper, "MESHFETCH0001c"))
        s3_bucket = log_entry["s3_bucket"]
        s3_key = log_entry["s3_key"]

        s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        assert s3_object
        assert s3_object["Metadata"]["mex-messagetype"] == "REPORT"
        assert s3_object["Metadata"]["mex-to"] == "MESH-TEST1"
        assert s3_object["Metadata"]["mex-workflowid"] == "TESTWORKFLOW"
        assert s3_object["Metadata"]["mex-statussuccess"] == "ERROR"

    @mock.patch.object(MeshFetchMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_fetch_file_chunk_app_gone_away_unhappy_path(
        self, mock_create_new_internal_id, mock_response
    ):
        """Test the lambda with unhappy path"""
        # Mock responses from MESH server
        mock_response.get(
            f"/messageexchange/MESH-TEST1/inbox/{MeshTestingCommon.KNOWN_MESSAGE_ID1}",
            text="",
            status_code=HTTPStatus.GONE.value,
            headers={
                "Content-Type": "application/json",
            },
        )

        mock_create_new_internal_id.return_value = MeshTestingCommon.KNOWN_INTERNAL_ID1
        s3_client = boto3.client("s3", region_name="eu-west-2")
        ssm_client = boto3.client("ssm", region_name="eu-west-2")
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        mock_input = self._sample_first_input_event()
        assert self.app
        try:
            self.app.main(event=mock_input, context=MeshTestingCommon.CONTEXT)
        except HTTPError:
            return
        self.fail("Failed to raise 410 Client Error")

    @staticmethod
    def _sample_first_input_event():
        return {
            "statusCode": HTTPStatus.OK.value,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "complete": False,
                "internal_id": MeshTestingCommon.KNOWN_INTERNAL_ID1,
                "message_id": MeshTestingCommon.KNOWN_MESSAGE_ID1,
                "dest_mailbox": "MESH-TEST1",
            },
        }
