"""Common methods and classes used for testing mesh client"""
from textwrap import dedent
from typing import ClassVar, Literal
from unittest import TestCase

from botocore.config import Config
from spine_aws_common.log.log_helper import LogHelper

FILE_CONTENT = "123456789012345678901234567890123"


def put_parameter(
    ssm_client,
    Name: str,
    Value: str,
    Type: Literal["String", "SecureString", "StringList"] = "String",
    Overwrite: bool = True,
):
    """Setup ssm param store for tests"""
    # Setup mapping
    ssm_client.put_parameter(Name=Name, Value=Value, Type=Type, Overwrite=Overwrite)


class MeshTestingCommon:
    """Mock helpers"""

    CONTEXT: ClassVar[dict[str, str]] = {"aws_request_id": "TESTREQUEST"}
    KNOWN_INTERNAL_ID = "20210701225219765177_TESTER"
    KNOWN_INTERNAL_ID1 = "20210701225219765177_TEST01"
    KNOWN_INTERNAL_ID2 = "20210701225219765177_TEST02"
    KNOWN_MESSAGE_ID1 = "20210704225941465332_MESG01"
    KNOWN_MESSAGE_ID2 = "20210705133616577537_MESG02"
    KNOWN_MESSAGE_ID3 = "20210705134726725149_MESG03"
    FILE_CONTENT = FILE_CONTENT

    aws_config = Config(region_name="eu-west-2")

    os_environ_values: ClassVar[dict[str, str]] = {
        "AWS_REGION": "eu-west-2",
        "AWS_EXECUTION_ENV": "AWS_Lambda_python3.8",
        "AWS_LAMBDA_FUNCTION_NAME": "lambda_test",
        "AWS_LAMBDA_FUNCTION_MEMORY_SIZE": "128",
        "AWS_LAMBDA_FUNCTION_VERSION": "1",
        "Environment": "meshtest",
        "CHUNK_SIZE": "10",
    }

    @classmethod
    def get_known_internal_id(cls):
        """Get a known internal Id for testing and mocking purposes"""
        return MeshTestingCommon.KNOWN_INTERNAL_ID

    @classmethod
    def get_known_internal_id1(cls):
        """Get a known internal Id for testing and mocking purposes"""
        return MeshTestingCommon.KNOWN_INTERNAL_ID1

    @classmethod
    def get_known_internal_id2(cls):
        """Get a known internal Id for testing and mocking purposes"""
        return MeshTestingCommon.KNOWN_INTERNAL_ID2

    @staticmethod
    def setup_step_function(sfn_client, environment, step_function_name):
        """Setup a mock step function with name from environment"""
        if not environment:
            environment = "default"
        step_func_definition = {
            "Comment": "Test step function",
            "StartAt": "HelloWorld",
            "States": {
                "HelloWorld": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:eu-west-2:123456789012:function:HW",
                    "End": True,
                }
            },
        }
        return sfn_client.create_state_machine(
            definition=f"{step_func_definition}",
            loggingConfiguration={
                "destinations": [{"cloudWatchLogsLogGroup": {"logGroupArn": "xxx"}}],
                "includeExecutionData": False,
                "level": "ALL",
            },
            name=step_function_name,
            roleArn="arn:aws:iam::123456789012:role/StepFunctionRole",
            tags=[{"key": "environment", "value": environment}],
            tracingConfiguration={"enabled": False},
            type="STANDARD",
        )

    @staticmethod
    def setup_mock_aws_s3_buckets(environment, s3_client):
        """Setup standard environment for tests"""
        location = {"LocationConstraint": "eu-west-2"}
        s3_client.create_bucket(
            Bucket=f"{environment}-mesh",
            CreateBucketConfiguration=location,
        )
        file_content = FILE_CONTENT
        s3_client.put_object(
            Bucket=f"{environment}-mesh",
            Key="MESH-TEST2/outbound/testfile.json",
            Body=file_content,
            Metadata={
                "Mex-subject": "Custom Subject",
            },
        )

    @staticmethod
    def setup_mock_aws_ssm_parameter_store(environment, ssm_client):
        """Setup ssm param store for tests"""
        # Setup mapping
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/mapping/{environment}-mesh/MESH-TEST2/outbound/src_mailbox",
            Value="MESH-TEST2",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/mapping/{environment}-mesh/MESH-TEST2/outbound/dest_mailbox",
            Value="MESH-TEST1",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/mapping/{environment}-mesh/MESH-TEST2/outbound/workflow_id",
            Value="TESTWORKFLOW",
        )
        # Setup secrets
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/MESH_URL",
            Value="https://localhost",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/MESH_SHARED_KEY",
            Value="BackBone",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/mailboxes/MESH-TEST1/MAILBOX_PASSWORD",
            Value="pwd123456",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/mailboxes/MESH-TEST1/INBOUND_BUCKET",
            Value=f"{environment}-mesh",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/mailboxes/MESH-TEST1/INBOUND_FOLDER",
            Value="inbound-mesh-test1",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/mailboxes/MESH-TEST2/MAILBOX_PASSWORD",
            Value="pwd123456",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/mailboxes/MESH-TEST2/INBOUND_BUCKET",
            Value=f"{environment}-mesh",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/mailboxes/MESH-TEST2/INBOUND_FOLDER",
            Value="inbound-mesh-test2",
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/MESH_VERIFY_SSL",
            Value="False",
        )
        # these are self signed certs
        ca_cert = dedent(
            """
            -----BEGIN CERTIFICATE-----
            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
            -----END CERTIFICATE-----
        """
        )
        client_cert = dedent(
            """
            -----BEGIN CERTIFICATE-----
            MIIFEjCCAvqgAwIBAgICEAEwDQYJKoZIhvcNAQELBQAwfzELMAkGA1UEBhMCR0Ix
            FzAVBgNVBAgMDldlc3QgWW9ya3NoaXJlMQ4wDAYDVQQHDAVMZWVkczENMAsGA1UE
            CgwEc3ViMTENMAsGA1UECwwETUVTSDEpMCcGA1UEAwwgY2xpZW50LXN1YjEtY2Eg
            LSBpbnRlcm1lZGlhdGUgQ0EwIBcNMjMwNTAzMjAxNjM5WhgPMjA3MzA0MjAyMDE2
            MzlaMIGiMQswCQYDVQQGEwJHQjEXMBUGA1UECAwOV2VzdCBZb3Jrc2hpcmUxDjAM
            BgNVBAcMBUxlZWRzMRswGQYDVQQKDBJTRUxGLVNJR05FRC1DTElFTlQxDjAMBgNV
            BAsMBVNwaW5lMRUwEwYDVQQDDAx2YWxpZC5jbGllbnQxJjAkBgkqhkiG9w0BCQEW
            F21lc2guc3BpbmVAaHNjaWMuZ292LnVrMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A
            MIIBCgKCAQEAnglDAf+LO7QhYZ0L6sDek3hghmaOA7eJ61XyMOJ06A+nxd8AfG4J
            TkJDQrIiJkBOaIEWhfI5zPYXmyN7EPcngS+RHGZyq+z6JXScfSIuAVNaWEp97r3f
            +4vuHRcDdu6B6hH4AFI4FCFXF7/QU3dBqBtDj88GnKAnhfF/1F3g/S7mboBq0yrv
            ZNGNqvHqLkgUyw33OC8yeT2k9/EDlBkpSvu8Yd9XekG8ctgibgz/vDfIpX9xCgYc
            KVjkzmHwJD/f6Kz2i+6+JSgLgLr4bjlb+4ZXfUWhMbnHIK6homny7lw3FmLp9zBA
            8sRwcQDvjKEg3CU+ndC9HfGeb8v1DQUF1QIDAQABo3IwcDAJBgNVHRMEAjAAMB0G
            A1UdDgQWBBS8f1V7djSQ4RDrXqNSpEJQUQ26djAfBgNVHSMEGDAWgBQwtjDMxLLP
            saCVv3mZW8q2G/f0TDAOBgNVHQ8BAf8EBAMCBeAwEwYDVR0lBAwwCgYIKwYBBQUH
            AwIwDQYJKoZIhvcNAQELBQADggIBALvG2jk12SxZYRzXCI+ZdQfdf0E9z+QXpFjD
            6PTq8SXYj5/p2vPhnGfaRtiPBsVcQHRhcv8SExbEGFEc7sEdRFExmZvdEU6LY6mQ
            FRLPig0Er1e/qnsEwCJJRm8n67dHnmRe8nvvKSwkcLsRMFuteBZWWU6Tb/TgO9wh
            04teN/bPrRrgHvuWm6FrvJBHHEfaqULLuVFsgyPewjN0AncUYITNZXJZzrw0kf6e
            BUmTV+9jbG4H7R/JD4wQW+VF9ITTFBb2DSvR7J902ZLeJ1qP2snCiMDQ5aeVrrSA
            Rf8Fg4xxBVuI7E9buG1NJXfmr0AQE9RlY4LA0/zgEsjUtKmrEYDHkJL7BX21DX6/
            b00o+DeB2B9Ui9pZ/z5+T03Vl8whbeJ+BJbwDPrQie8uIZQF5tmCD+vyWzLDNvwt
            Z+QGcn/4Yr/iouiq4H3XgP7/TqOUBUQ+ECgPmcbSOSy68RvLgzOa58gGya0MsLuc
            rI41TfiR1lphhtMFXy8TDW0Mz8b4qo9YW5afFlz1TXfPiOk92fXYJyPYJ+h/zD6V
            lIXp3tmGoeXl50MvbGyl5LcqxFIkU8/heJTpyimSwxxSNFxt4pPxCwE4fwTLXi6C
            xyaxH0a8c//r2zw2FooG9BZptcsXSKaj6Bgrb9Tw7O+5pR2fJ6PUSyN6zrfEzOUH
            zkLccDHF
            -----END CERTIFICATE-----
        """
        )

        client_key = dedent(
            """
            -----BEGIN PRIVATE KEY-----
            MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCeCUMB/4s7tCFh
            nQvqwN6TeGCGZo4Dt4nrVfIw4nToD6fF3wB8bglOQkNCsiImQE5ogRaF8jnM9heb
            I3sQ9yeBL5EcZnKr7PoldJx9Ii4BU1pYSn3uvd/7i+4dFwN27oHqEfgAUjgUIVcX
            v9BTd0GoG0OPzwacoCeF8X/UXeD9LuZugGrTKu9k0Y2q8eouSBTLDfc4LzJ5PaT3
            8QOUGSlK+7xh31d6Qbxy2CJuDP+8N8ilf3EKBhwpWOTOYfAkP9/orPaL7r4lKAuA
            uvhuOVv7hld9RaExuccgrqGiafLuXDcWYun3MEDyxHBxAO+MoSDcJT6d0L0d8Z5v
            y/UNBQXVAgMBAAECggEANHktyx2PHQlP5invmYhlvwCCyE2IDPrlrALTEmE24RDF
            q8FCV45vv5Dn5V7hUOMcRb3K/Tmy8Her2eK7i6QM9WuWWqA3phde7Y3dIf112hHT
            lypQyzM3ij3pl7Ya++Pwtgg2WODz5tc1JFkXsocQAWHgGoFqmBnjVamcwKZVPKtO
            2hTDq7nioVF8+PeuaTlPwKZE9yVhTUJRyI0gCowytkYq/NVVtTstt9c9kbgOBUN1
            8dBbCRqPZ+iw+PFYFRTEyJQAADVGqmTCZ/gUNF+sZSv4ymhdQswdg1JdZqfwrhOJ
            RkuWuyr8yfkzan/zJ0/Cl/21nJVV3Y71evZsLItQ5wKBgQDLbLXLOuKLUCclWOyb
            2xegQNVJryTWoodzf9xdSy7U7mud6vjr5HyVGQzh4XRiA8ngvW8M3kVAlPMQzoMN
            s7zRBAIngGXllJmBJfD6aeuoFWOqOf0aldjCKkFE8bIBY5EXQBpWrEjAX/I07w9e
            vUdtRKmYSZJjh/DJnNK4d4/BVwKBgQDG4X2p1HyS45bDazfk+z9cbd5s95q9B2o/
            V0JLYoeTaFKrlzIPKC+NRxDB6tPsdkEs0D5PRZlDsH122l4m4sga8RrSqoKPMZtf
            NjatCvIsGRg8fwn3aQjYH4oZl3NMyvXELSpbrFc2Qg75OXJlbO+fayyxBn+4OehN
            UoBO9FIaswKBgDVhy7sPMs/4Mq2cTksADY0iNlZlvbcNY5otnXhl+F4sStVgCf5t
            MTw3HKhR76ag8+MkEvY/hdDSxY5NgxqfZhc7hA01poe+nSHFAR3Vmd+77TGIkiDd
            3cnmKMac3md652JAkijYgSbqhrbZXSExboMAF7k85Ut1KvzdSHbb+T91AoGBAICY
            fTC6/HHeRzXEtjeRXb7eK9w5ngxsJv8d5PfpldByvEHHWc8DJPws32ED/lP/gtT/
            McsALcHe9MFNIWPzb4A8NiPRrOn6IYTHAUOSuFRbRZiYbFFV0Sot+pXhn+QfuBpJ
            OgJcxWeH/zaXNqjub2KdYiB1G1B74QFePyjOQeiRAoGBAIbm+e+b+2UJhDlCe5ft
            sJpjqtKyLA437t7Q/VdKztjHJw2sHG6YUSi6no9TL6zqnE+B0VQtQGwRyiShACN2
            RIrg71/i4fAqbRv1Zrfkd4Jaq/M5qKTl6NVx7Pgs6n/qhKXv0mdeSFpjSu0BL4X7
            3VfrFGSvc26+6hy74NPSPEg6
            -----END PRIVATE KEY-----
        """
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/MESH_CA_CERT",
            Value=ca_cert,
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/MESH_CLIENT_CERT",
            Value=client_cert,
        )
        put_parameter(
            ssm_client,
            Name=f"/{environment}/mesh/MESH_CLIENT_KEY",
            Value=client_key,
        )


class MeshTestCase(TestCase):
    """Common setup for Mesh test cases"""

    def __init__(self, method_name):
        super().__init__(methodName=method_name)
        self.environment = None
        self.app = None

    def setUp(self):
        """Common setup for all tests"""
        self.log_helper = LogHelper()
        self.log_helper.set_stdout_capture()

    def tearDown(self):
        self.log_helper.clean_up()
