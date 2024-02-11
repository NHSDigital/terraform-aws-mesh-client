""" Testing MeshSendMessageChunk Application """

import json
import sys
from http import HTTPStatus
from unittest import mock

import boto3
import pytest
import requests_mock
from mesh_send_message_chunk_application import (
    MaxByteExceededException,
    MeshSendMessageChunkApplication,
)
from moto import mock_s3, mock_secretsmanager, mock_ssm, mock_stepfunctions

from .mesh_check_send_parameters_application_test import sample_trigger_event
from .mesh_testing_common import (
    FILE_CONTENT,
    MeshTestCase,
    MeshTestingCommon,
)


@mock_secretsmanager
@mock_ssm
@mock_s3
@mock_stepfunctions
class TestMeshSendMessageChunkApplication(MeshTestCase):
    """Testing MeshSendMessageChunk application"""

    FILE_CONTENT = "123456789012345678901234567890123"
    FILE_SIZE = len(FILE_CONTENT)

    MEBIBYTE = 1024 * 1024
    DEFAULT_BUFFER_SIZE = 20 * MEBIBYTE

    @mock.patch.dict("os.environ", MeshTestingCommon.os_environ_values)
    def setUp(self):
        """Override setup to use correct application object"""
        super().setUp()
        self.app = MeshSendMessageChunkApplication()
        self.environment = self.app.system_config["ENVIRONMENT"]

    @mock.patch.object(MeshSendMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_send_file_chunk_app_no_chunks_happy_path(
        self, mock_create_new_internal_id, response_mocker
    ):
        assert self.app
        self.app.config.crumb_size = sys.maxsize
        self.app.config.chunk_size = sys.maxsize
        """Test the lambda with small file, no chunking, happy path"""
        mock_create_new_internal_id.return_value = MeshTestingCommon.KNOWN_INTERNAL_ID

        response_mocker.post(
            "/messageexchange/MESH-TEST2/outbox",
            text=json.dumps({"message_id": "20210711164906010267_97CCD9"}),
            headers={
                "Content-Type": "application/json",
                "Content-Length": "44",
                "Connection": "keep-alive",
            },
            request_headers={
                "mex-subject": "Custom Subject",
            },
        )
        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        mock_lambda_input = self._sample_single_chunk_input_event()
        expected_lambda_response = self._sample_single_chunk_input_event()
        expected_lambda_response["body"].update({"complete": True})
        expected_lambda_response["body"].update(
            {"current_byte_position": len(FILE_CONTENT)}
        )
        assert self.app
        try:
            lambda_response = self.app.main(
                event=mock_lambda_input, context=MeshTestingCommon.CONTEXT
            )
        except Exception as e:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {e!s}")

        lambda_response["body"].pop("message_id")

        assert lambda_response == expected_lambda_response
        # Check completion
        assert self.log_helper.was_value_logged("LAMBDA0003", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHSEND0008", "Log_Level", "INFO")

    @mock.patch.object(MeshSendMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_send_file_chunk_app_2_chunks_happy_path(
        self,
        mock_create_new_internal_id,
        response_mocker,
    ):
        """Test the lambda with small file, in 4 chunks, happy path"""
        mock_create_new_internal_id.return_value = MeshTestingCommon.KNOWN_INTERNAL_ID

        custom_request_headers = {
            "mex-subject": "Custom Subject",
        }
        response_mocker.post(
            "/messageexchange/MESH-TEST2/outbox",
            text=json.dumps({"message_id": "20210711164906010267_97CCD9"}),
            headers={
                "Content-Type": "application/json",
                "Content-Length": "33",
                "Connection": "keep-alive",
            },
            request_headers=custom_request_headers,
        )
        response_mocker.post(
            "/messageexchange/MESH-TEST2/outbox/20210711164906010267_97CCD9/2",
        )
        response_mocker.post(
            "/messageexchange/MESH-TEST2/outbox/20210711164906010267_97CCD9/3",
        )
        response_mocker.post(
            "/messageexchange/MESH-TEST2/outbox/20210711164906010267_97CCD9/4",
        )
        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        mock_input = self._sample_multi_chunk_input_event()
        mock_response = self._sample_multi_chunk_input_event()
        mock_response["body"].update({"complete": True})
        mock_response["body"]["send_params"].update({"compress": True, "chunked": True})
        mock_response["body"].update({"chunk_number": 4})
        assert self.app
        count = 1
        while not mock_input["body"]["complete"]:
            chunk_number = mock_input["body"].get("chunk_number", 1)
            print(f">>>>>>>>>>> Chunk {chunk_number} >>>>>>>>>>>>>>>>>>>>")
            try:
                response = self.app.main(
                    event=mock_input, context=MeshTestingCommon.CONTEXT
                )
            except Exception as exception:  # pylint: disable=broad-except
                # need to fail happy pass on any exception
                self.fail(f"Invocation crashed with Exception {exception!s}")
            if count == 1:
                message_id = response["body"]["message_id"]
            count = count + 1
            mock_input = response
            print(response)

        mock_response["body"]["message_id"] = message_id

        response = mock_response

        # Check completion
        assert self.log_helper.was_value_logged("LAMBDA0003", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHSEND0008", "Log_Level", "INFO")

    @mock.patch.object(MeshSendMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_send_file_chunk_app_too_many_chunks(
        self, mock_create_new_internal_id, fake_mesh_server
    ):
        """Test lambda throws MaxByteExceededException when too many chunks specified"""
        mock_create_new_internal_id.return_value = MeshTestingCommon.KNOWN_INTERNAL_ID

        fake_mesh_server.post(
            "/messageexchange/MESH-TEST2/outbox",
            text=json.dumps({"message_id": "20210711164906010267_97CCD9"}),
            headers={
                "Content-Type": "application/json",
                "Content-Length": "33",
                "Connection": "keep-alive",
            },
        )

        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        mock_input = self._sample_too_many_chunks_input_event()
        mock_response = self._sample_too_many_chunks_input_event()
        mock_response["body"].update({"complete": True})
        mock_response["body"]["send_params"].update({"compress": True})
        assert self.app
        with pytest.raises(MaxByteExceededException) as context:
            self.app.main(event=mock_input, context=MeshTestingCommon.CONTEXT)
        assert isinstance(context.value, MaxByteExceededException)

    @mock.patch.object(MeshSendMessageChunkApplication, "_create_new_internal_id")
    @requests_mock.Mocker()
    def test_mesh_send_file_chunk_app_no_chunks_invoke_via_eventbridge(
        self, mock_create_new_internal_id, response_mocker
    ):
        assert self.app
        self.app.config.crumb_size = sys.maxsize
        self.app.config.chunk_size = sys.maxsize
        """Test the lambda with small file, no chunking, happy path"""
        mock_create_new_internal_id.return_value = MeshTestingCommon.KNOWN_INTERNAL_ID

        response_mocker.post(
            "/messageexchange/MESH-TEST2/outbox",
            text=json.dumps({"message_id": "20210711164906010267_97CCD9"}),
            headers={
                "Content-Type": "application/json",
                "Content-Length": "44",
                "Connection": "keep-alive",
            },
            request_headers={
                "mex-subject": "Custom Subject",
            },
        )
        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )

        expected_lambda_response = self._sample_output_invoked_via_event_bridge()
        expected_lambda_response["body"].update({"complete": True})
        expected_lambda_response["body"].update(
            {"current_byte_position": len(FILE_CONTENT)}
        )
        sfn_client = boto3.client("stepfunctions", config=MeshTestingCommon.aws_config)
        response = MeshTestingCommon.setup_step_function(
            sfn_client,
            self.environment,
            f"{self.environment}-send-message",
        )
        step_func_arn = response.get("stateMachineArn", None)
        assert step_func_arn is not None

        response = sfn_client.start_execution(
            stateMachineArn=step_func_arn,
            input=json.dumps(sample_trigger_event()),
        )
        step_func_exec_arn = response.get("executionArn", None)
        assert step_func_exec_arn is not None
        assert self.app

        try:
            lambda_response = self.app.main(
                event=sample_trigger_event(), context=MeshTestingCommon.CONTEXT
            )
        except Exception as e:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {e!s}")

        lambda_response["body"].pop("message_id")

        assert lambda_response == expected_lambda_response
        # Check completion
        assert self.log_helper.was_value_logged("MESHSEND0002", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHSEND0008", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("LAMBDA0003", "Log_Level", "INFO")

    def _sample_single_chunk_input_event(self):
        """Return Example input event"""
        return {
            "statusCode": HTTPStatus.OK.value,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "internal_id": MeshTestingCommon.KNOWN_INTERNAL_ID,
                "src_mailbox": "MESH-TEST2",
                "dest_mailbox": "MESH-TEST1",
                "workflow_id": "TESTWORKFLOW",
                "bucket": f"{self.environment}-mesh",
                "key": "MESH-TEST2/outbound/testfile.json",
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
                    "recipient": "MESH-TEST1",
                    "s3_bucket": "meshtest-mesh",
                    "s3_key": "MESH-TEST2/outbound/testfile.json",
                    "sender": "MESH-TEST2",
                    "subject": "Custom Subject",
                    "total_chunks": 1,
                    "workflow_id": "TESTWORKFLOW",
                },
            },
        }

    def _sample_multi_chunk_input_event(self):
        """Return Example input event"""
        return {
            "statusCode": HTTPStatus.OK.value,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "internal_id": MeshTestingCommon.KNOWN_INTERNAL_ID,
                "src_mailbox": "MESH-TEST2",
                "dest_mailbox": "MESH-TEST1",
                "workflow_id": "TESTWORKFLOW",
                "bucket": f"{self.environment}-mesh",
                "key": "MESH-TEST2/outbound/testfile.json",
                "chunked": True,
                "chunk_number": 1,
                "total_chunks": 4,
                "complete": False,
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
                    "filename": "testfile.json",
                    "local_id": None,
                    "partner_id": None,
                    "recipient": "MESH-TEST1",
                    "s3_bucket": f"{self.environment}-mesh",
                    "s3_key": "MESH-TEST2/outbound/testfile.json",
                    "sender": "MESH-TEST2",
                    "subject": "Custom Subject",
                    "total_chunks": 4,
                    "workflow_id": "TESTWORKFLOW",
                },
            },
        }

    def _sample_too_many_chunks_input_event(self):
        """Return Example input event"""
        return {
            "statusCode": HTTPStatus.OK.value,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "internal_id": MeshTestingCommon.KNOWN_INTERNAL_ID,
                "src_mailbox": "MESH-TEST2",
                "dest_mailbox": "MESH-TEST1",
                "workflow_id": "TESTWORKFLOW",
                "bucket": f"{self.environment}-mesh",
                "key": "MESH-TEST2/outbound/testfile.json",
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
                    "recipient": "MESH-TEST1",
                    "s3_bucket": f"{self.environment}-mesh",
                    "s3_key": "MESH-TEST2/outbound/testfile.json",
                    "sender": "MESH-TEST2",
                    "subject": "Custom Subject",
                    "total_chunks": 2,
                    "workflow_id": "TESTWORKFLOW",
                },
            },
        }

    def _sample_input_event_multi_chunk(self):
        """Return Example input event"""
        return {
            "statusCode": HTTPStatus.OK.value,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "internal_id": MeshTestingCommon.KNOWN_INTERNAL_ID,
                "src_mailbox": "MESH-TEST2",
                "dest_mailbox": "MESH-TEST1",
                "workflow_id": "TESTWORKFLOW",
                "bucket": f"{self.environment}-mesh",
                "key": "MESH-TEST2/outbound/testfile.json",
                "chunked": True,
                "chunk_number": 1,
                "total_chunks": 3,
                "chunk_size": 14,
                "complete": False,
                "current_byte_position": 0,
                "will_compress": False,
            },
        }

    def _sample_output_invoked_via_event_bridge(self):
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "chunk_number": 1,
                "complete": True,
                "current_byte_position": 33,
                "internal_id": "20210701225219765177_TESTER",
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
                    "recipient": "MESH-TEST1",
                    "s3_bucket": "meshtest-mesh",
                    "s3_key": "MESH-TEST2/outbound/testfile.json",
                    "sender": "MESH-TEST2",
                    "subject": "Custom Subject",
                    "total_chunks": 1,
                    "workflow_id": "TESTWORKFLOW",
                },
            },
        }
