""" Testing MeshPollMailbox application """

import json
import sys
from http import HTTPStatus
from unittest import mock
from uuid import uuid4

import boto3
from mesh_check_send_parameters_application import (
    MeshCheckSendParametersApplication,
)
from moto import mock_s3, mock_secretsmanager, mock_ssm, mock_stepfunctions
from shared.common import SingletonCheckFailure

from .mesh_testing_common import (
    MeshTestCase,
    MeshTestingCommon,
)


@mock_secretsmanager
@mock_ssm
@mock_s3
@mock_stepfunctions
class TestMeshCheckSendParametersApplication(MeshTestCase):
    """Testing MeshPollMailbox application"""

    @mock.patch.dict("os.environ", MeshTestingCommon.os_environ_values)
    def setUp(self):
        """Override setup to use correct application object"""
        super().setUp()
        self.app = MeshCheckSendParametersApplication()
        self.environment = self.app.system_config["ENVIRONMENT"]

    def setup_mock_aws_environment(self, s3_client, ssm_client):
        """Setup standard environment for tests"""
        location = {"LocationConstraint": "eu-west-2"}
        s3_client.create_bucket(
            Bucket=f"{self.environment}-mesh",
            CreateBucketConfiguration=location,
        )
        file_content = "123456789012345678901234567890123"
        s3_client.put_object(
            Bucket=f"{self.environment}-mesh",
            Key="MESH-TEST2/outbound/testfile.json",
            Body=file_content,
        )
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )

    @mock.patch.object(
        MeshCheckSendParametersApplication,
        "_get_internal_id",
        MeshTestingCommon.get_known_internal_id1,
    )
    def test_mesh_check_send_parameters_happy_path_chunked(self):
        """Test the lambda as a whole, happy path for small file"""
        assert self.app
        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        self.setup_mock_aws_environment(s3_client, ssm_client)
        sfn_client = boto3.client("stepfunctions", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_step_function(
            sfn_client,
            self.environment,
            f"{self.environment}-send-message",
        )

        mock_response = {
            "statusCode": HTTPStatus.OK.value,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "internal_id": MeshTestingCommon.KNOWN_INTERNAL_ID1,
                "src_mailbox": "MESH-TEST2",
                "dest_mailbox": "MESH-TEST1",
                "workflow_id": "TESTWORKFLOW",
                "bucket": f"{self.environment}-mesh",
                "key": "MESH-TEST2/outbound/testfile.json",
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
                    "recipient": "MESH-TEST1",
                    "s3_bucket": "meshtest-mesh",
                    "s3_key": "MESH-TEST2/outbound/testfile.json",
                    "sender": "MESH-TEST2",
                    "subject": None,
                    "total_chunks": 4,
                    "workflow_id": "TESTWORKFLOW",
                },
            },
        }
        assert self.app
        try:
            response = self.app.main(
                event=sample_trigger_event(), context=MeshTestingCommon.CONTEXT
            )
        except Exception as e:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {e!s}")

        assert response == mock_response
        assert self.log_helper.was_value_logged("LAMBDA0001", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("LAMBDA0002", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("LAMBDA0003", "Log_Level", "INFO")

    @mock.patch.object(
        MeshCheckSendParametersApplication,
        "_get_internal_id",
        MeshTestingCommon.get_known_internal_id1,
    )
    def test_mesh_check_send_parameters_happy_path_unchunked(self):
        """Test the lambda as a whole, happy path for small file"""
        assert self.app
        self.app.config.crumb_size = sys.maxsize
        self.app.config.chunk_size = sys.maxsize

        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        self.setup_mock_aws_environment(s3_client, ssm_client)
        sfn_client = boto3.client("stepfunctions", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_step_function(
            sfn_client,
            self.environment,
            f"{self.environment}-send-message",
        )

        mock_response = {
            "statusCode": HTTPStatus.OK.value,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "internal_id": MeshTestingCommon.KNOWN_INTERNAL_ID1,
                "src_mailbox": "MESH-TEST2",
                "dest_mailbox": "MESH-TEST1",
                "workflow_id": "TESTWORKFLOW",
                "bucket": f"{self.environment}-mesh",
                "key": "MESH-TEST2/outbound/testfile.json",
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
                    "recipient": "MESH-TEST1",
                    "s3_bucket": "meshtest-mesh",
                    "s3_key": "MESH-TEST2/outbound/testfile.json",
                    "sender": "MESH-TEST2",
                    "subject": None,
                    "total_chunks": 1,
                    "workflow_id": "TESTWORKFLOW",
                },
            },
        }
        assert self.app
        try:
            response = self.app.main(
                event=sample_trigger_event(), context=MeshTestingCommon.CONTEXT
            )
        except Exception as e:  # pylint: disable=broad-except
            # need to fail happy pass on any exception
            self.fail(f"Invocation crashed with Exception {e!s}")

        assert response == mock_response
        assert self.log_helper.was_value_logged("LAMBDA0001", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("LAMBDA0002", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("LAMBDA0003", "Log_Level", "INFO")

    def _singleton_test_setup(self):
        """Setup for singleton test"""
        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        self.setup_mock_aws_environment(s3_client, ssm_client)
        sfn_client = boto3.client("stepfunctions", config=MeshTestingCommon.aws_config)
        return sfn_client

    @mock.patch.object(
        MeshCheckSendParametersApplication,
        "_get_internal_id",
        MeshTestingCommon.get_known_internal_id,
    )
    def test_running_as_singleton(self):
        """
        Test that the singleton check works correctly
        """
        sfn_client = self._singleton_test_setup()

        print("------------------------- TEST 1 -------------------------------")
        # define step function
        response = MeshTestingCommon.setup_step_function(
            sfn_client,
            self.environment,
            f"{self.environment}-send-message",
        )
        step_func_arn = response.get("stateMachineArn", None)
        assert step_func_arn is not None

        # 'start' fake state machine
        response = sfn_client.start_execution(
            stateMachineArn=step_func_arn,
            input=json.dumps(sample_trigger_event()),
        )
        step_func_exec_arn = response.get("executionArn", None)
        assert step_func_exec_arn is not None
        assert self.app
        # do running check - should pass (1 step function running, just mine)
        try:
            response = self.app.main(
                event=sample_trigger_event(), context=MeshTestingCommon.CONTEXT
            )
        except SingletonCheckFailure as e:
            self.fail(e.msg)
        assert response is not None
        assert not self.log_helper.was_value_logged(
            "MESHSEND0003", "Log_Level", "ERROR"
        )
        assert self.log_helper.was_value_logged("MESHSEND0004", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHSEND0004a", "Log_Level", "INFO")
        self.log_helper.clean_up()

        print("------------------------- TEST 2 -------------------------------")
        self.log_helper.set_stdout_capture()

        # create another step function with a different name
        response = MeshTestingCommon.setup_step_function(
            sfn_client,
            self.environment,
            f"{self.environment}-get-messages",
        )
        step_func2_arn = response.get("stateMachineArn", None)
        assert step_func2_arn is not None

        # 'start' state machine 2 with my mailbox
        response = sfn_client.start_execution(
            stateMachineArn=step_func2_arn,
            input=json.dumps(sample_trigger_event()),
        )
        step_func_exec_arn = response.get("executionArn", None)
        assert step_func_exec_arn is not None

        # do running check - should pass (1 step function of my name with my mailbox)
        try:
            response = self.app.main(
                event=sample_trigger_event(), context=MeshTestingCommon.CONTEXT
            )
        except SingletonCheckFailure as e:
            self.fail(e.msg)
        assert response is not None
        assert not self.log_helper.was_value_logged(
            "MESHSEND0003", "Log_Level", "ERROR"
        )
        assert self.log_helper.was_value_logged("MESHSEND0004", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHSEND0004a", "Log_Level", "INFO")
        self.log_helper.clean_up()

        print("------------------------- TEST 3 -------------------------------")
        self.log_helper.set_stdout_capture()

        # 'start' state machine with different mailbox
        response = sfn_client.start_execution(
            stateMachineArn=step_func_arn,
            input=json.dumps(
                sample_trigger_event(f"MESH-TEST2/outbound/{uuid4().hex}.json")
            ),
        )
        step_func_exec_arn = response.get("executionArn", None)
        assert step_func_exec_arn is not None

        # do running check - should pass (1 step function running with my mailbox)
        try:
            response = self.app.main(
                event=sample_trigger_event(), context=MeshTestingCommon.CONTEXT
            )
        except SingletonCheckFailure as e:
            self.fail(e.msg)
        assert response is not None
        assert not self.log_helper.was_value_logged(
            "MESHSEND0003", "Log_Level", "ERROR"
        )
        assert self.log_helper.was_value_logged("MESHSEND0004", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHSEND0004a", "Log_Level", "INFO")
        self.log_helper.clean_up()

        print("------------------------- TEST 4 -------------------------------")
        self.log_helper.set_stdout_capture()

        # 'start' another instance with same mailbox as mine
        response = sfn_client.start_execution(
            stateMachineArn=step_func_arn,
            input=json.dumps(sample_trigger_event()),
        )
        step_func_exec_arn = response.get("executionArn", None)
        assert step_func_exec_arn is not None
        # do running check - should return 503 and log MESHSEND0003 error message
        response = self.app.main(
            event=sample_trigger_event(), context=MeshTestingCommon.CONTEXT
        )
        expected_return_code = {"statusCode": HTTPStatus.TOO_MANY_REQUESTS.value}
        expected_header = {"Retry-After": 18000}
        assert response == {**response, **expected_return_code}
        assert response["headers"] == {**response["headers"], **expected_header}
        assert self.log_helper.was_value_logged("MESHSEND0003", "Log_Level", "ERROR")
        assert not self.log_helper.was_value_logged("MESHSEND0004", "Log_Level", "INFO")
        assert self.log_helper.was_value_logged("MESHSEND0004a", "Log_Level", "INFO")


def sample_trigger_event(key: str = "MESH-TEST2/outbound/testfile.json"):
    """Return Example S3 eventbridge event"""
    return_value = {
        "version": "0",
        "id": "daea9bec-2d16-e943-2079-4d19b6e2ec1d",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2021-06-29T14:10:55Z",
        "region": "eu-west-2",
        "resources": [],
        "detail": {
            "eventVersion": "1.08",
            "eventTime": "2021-06-29T14:10:55Z",
            "eventSource": "s3.amazonaws.com",
            "eventName": "PutObject",
            "awsRegion": "eu-west-2",
            "requestParameters": {
                "X-Amz-Date": "20210629T141055Z",
                "bucketName": "meshtest-mesh",
                "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
                "x-amz-acl": "private",
                "X-Amz-SignedHeaders": "content-md5;content-type;host;x-amz-acl;x-amz-storage-class",  # pylint: disable=line-too-long
                "Host": "meshtest-mesh.s3.eu-west-2.amazonaws.com",
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
                    "ARN": "arn:aws:s3:::meshtest-mesh",
                },
            ],
            "eventType": "AwsApiCall",
            "managementEvent": False,
            "recipientAccountId": "123456789012",
            "eventCategory": "Data",
        },
    }
    # pylint: enable=line-too-long
    return return_value
