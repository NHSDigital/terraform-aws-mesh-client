""" Testing Get File From S3 Function """

from unittest import mock

import boto3
from mesh_send_message_chunk_application import (
    MeshSendMessageChunkApplication,
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
class TestMeshGetFileFromS3(MeshTestCase):
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

    def test_get_file_from_s3_with_parts(self):
        """
        Test _get_file_from_s3 getting an uncompressed large file
        """

        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        s3_resource = boto3.resource("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        assert self.app
        self.app.current_byte = 0

        self.app.s3_object = s3_resource.Object(
            f"{self.environment}-mesh", "MESH-TEST2/outbound/testfile.json"
        )
        self.app.config.crumb_size = 7
        self.app.config.chunk_size = self.app.s3_object.content_length * 2
        gen = self.app._get_chunk_from_s3()
        assert next(gen) == b"1234567"
        assert next(gen) == b"8901234"
        assert next(gen) == b"5678901"
        assert next(gen) == b"2345678"
        assert next(gen) == b"90123"

    def test_get_file_from_s3_without_parts(self):
        """
        Test _get_file_from_s3 getting an uncompressed small file
        """
        # FILE_CONTENT = "123456789012345678901234567890123"
        s3_client = boto3.client("s3", config=MeshTestingCommon.aws_config)
        s3_resource = boto3.resource("s3", config=MeshTestingCommon.aws_config)
        ssm_client = boto3.client("ssm", config=MeshTestingCommon.aws_config)
        MeshTestingCommon.setup_mock_aws_s3_buckets(self.environment, s3_client)
        MeshTestingCommon.setup_mock_aws_ssm_parameter_store(
            self.environment, ssm_client
        )
        assert self.app
        self.app.current_byte = 0

        self.app.s3_object = s3_resource.Object(
            f"{self.environment}-mesh", "MESH-TEST2/outbound/testfile.json"
        )
        self.app.config.crumb_size = self.app.s3_object.content_length + 1
        self.app.config.chunk_size = self.app.s3_object.content_length * 2
        gen = self.app._get_chunk_from_s3()
        all_33_bytes = next(gen)
        assert all_33_bytes == b"123456789012345678901234567890123"
