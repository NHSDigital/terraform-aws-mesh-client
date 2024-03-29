""" Testing MeshPollMailbox application """

import json
from http import HTTPStatus
from unittest import mock

import boto3
import requests_mock
from mesh_poll_mailbox_application import (
    MeshPollMailboxApplication,
)
from moto import mock_s3, mock_secretsmanager, mock_ssm, mock_stepfunctions

from .mesh_testing_common import (
    MeshTestCase,
    MeshTestingCommon,
)


@mock_secretsmanager
@mock_ssm
@mock_s3
@mock_stepfunctions
class TestMeshPollMailboxApplication(MeshTestCase):
    """Testing MeshPollMailbox application"""

    @mock.patch.dict("os.environ", MeshTestingCommon.os_environ_values)
    def setUp(self):
        """Override setup to use correct application object"""
        super().setUp()
        self.app = MeshPollMailboxApplication()
        self.environment = self.app.system_config["ENVIRONMENT"]

    @requests_mock.Mocker()
    def test_mesh_poll_mailbox_happy_path(self, mock_response):
        """Test the lambda"""

        # Mock response from MESH server
        mock_response.get(
            "/messageexchange/MESH-TEST1/inbox",
            text=json.dumps(
                {
                    "messages": [
                        MeshTestingCommon.KNOWN_MESSAGE_ID1,
                        MeshTestingCommon.KNOWN_MESSAGE_ID2,
                        MeshTestingCommon.KNOWN_MESSAGE_ID3,
                    ]
                }
            ),
        )

        mailbox_name = "MESH-TEST1"
        mock_input = {"mailbox": mailbox_name}
        s3_client = boto3.client("s3", region_name="eu-west-2")
        ssm_client = boto3.client("ssm", region_name="eu-west-2")
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        sfn_client = boto3.client("stepfunctions", region_name="eu-west-2")
        assert self.app
        response = MeshTestingCommon.setup_step_function(
            sfn_client,
            self.environment,
            f"{self.environment}-get-messages",
        )
        step_func_arn = response.get("stateMachineArn", None)
        assert step_func_arn is not None
        sfn_client.start_execution(
            stateMachineArn=step_func_arn,
            input=json.dumps(mock_input),
        )
        try:
            response = self.app.main(
                event=mock_input, context=MeshTestingCommon.CONTEXT
            )
        except Exception as e:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {e!s}")

        assert response["statusCode"] == int(HTTPStatus.OK)
        # check 3 messages received
        assert response["body"]["message_count"] == 3
        # check first message format in message_list
        assert (
            response["body"]["message_list"][0]["body"]["message_id"]
            == MeshTestingCommon.KNOWN_MESSAGE_ID1
        )
        assert False is response["body"]["message_list"][0]["body"]["complete"]
        assert (
            response["body"]["message_list"][0]["body"]["dest_mailbox"] == mailbox_name
        )

        # check the correct logs exist
        self.assertLogs("LAMBDA0001", level="INFO")
        self.assertLogs("LAMBDA0002", level="INFO")
        self.assertLogs("LAMBDA0003", level="INFO")
        self.assertLogs("MESHPOLL0001", level="INFO")

    @requests_mock.Mocker()
    def test_mesh_poll_mailbox_singleton_check(self, mock_response):
        """Test the lambda"""

        # Mock response from MESH server
        mock_response.get(
            "/messageexchange/MESH-TEST1/inbox",
            text=json.dumps(
                {
                    "messages": [
                        MeshTestingCommon.KNOWN_MESSAGE_ID1,
                        MeshTestingCommon.KNOWN_MESSAGE_ID2,
                        MeshTestingCommon.KNOWN_MESSAGE_ID3,
                    ]
                }
            ),
        )

        mailbox_name = "MESH-TEST1"
        mock_input = {"mailbox": mailbox_name}
        s3_client = boto3.client("s3", region_name="eu-west-2")
        ssm_client = boto3.client("ssm", region_name="eu-west-2")
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        sfn_client = boto3.client("stepfunctions", region_name="eu-west-2")
        assert self.app
        response = MeshTestingCommon.setup_step_function(
            sfn_client,
            self.environment,
            f"{self.environment}-get-messages",
        )
        step_func_arn = response.get("stateMachineArn", None)
        assert step_func_arn is not None
        sfn_client.start_execution(
            stateMachineArn=step_func_arn,
            input=json.dumps(mock_input),
        )
        sfn_client.start_execution(
            stateMachineArn=step_func_arn,
            input=json.dumps(mock_input),
        )
        sfn_client.start_execution(
            stateMachineArn=step_func_arn,
            input=json.dumps(mock_input),
        )
        try:
            response = self.app.main(
                event=mock_input, context=MeshTestingCommon.CONTEXT
            )
        except Exception as e:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {e!s}")

        assert response["statusCode"] == int(HTTPStatus.TOO_MANY_REQUESTS)
