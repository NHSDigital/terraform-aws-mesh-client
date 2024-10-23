from dataclasses import asdict
from http import HTTPStatus
from typing import Any

from shared.application import MESHLambdaApplication
from shared.common import (
    LockExists,
    return_failure,
)
from shared.send_parameters import get_send_parameters
from spine_aws_common.utilities import human_readable_bytes


class MeshCheckSendParametersApplication(MESHLambdaApplication):
    """MESH API Lambda for sending a message"""

    def __init__(self, additional_log_config=None, load_ssm_params=False):
        """Initialise variables"""
        super().__init__(additional_log_config, load_ssm_params)
        self.response: dict[str, Any] = {}

    def _get_internal_id(self):
        """Override to stop crashing when getting from non-dict event"""
        return self._create_new_internal_id()

    def start(self):

        self.log_object.write_log(
            "MESHSEND0004b",
            None,
            {"debug_str": str(self.event.raw_event)},
        )

        event_details = self.event["EventDetail"]["detail"]
        execution_id = self.event.get("ExecutionId")

        # in case of crash, set to internal server error so next stage fails
        self.response = {"statusCode": int(HTTPStatus.INTERNAL_SERVER_ERROR)}

        bucket = event_details["requestParameters"]["bucketName"]
        key = event_details["requestParameters"]["key"]

        self.log_object.write_log("MESHSEND0001", None, {"bucket": bucket, "file": key})

        s3_object = self.s3.Object(bucket, key)

        send_params = get_send_parameters(s3_object, self.config, self.ssm)

        self.log_object.write_log(
            "MESHSEND0004a",
            None,
            {
                "src_mailbox": send_params.sender,
                "dest_mailbox": send_params.recipient,
                "workflow_id": send_params.workflow_id,
            },
        )

        self.log_object.write_log(
            "MESHSEND0002",
            None,
            {
                "mailbox": send_params.sender,
                "bucket": send_params.s3_bucket,
                "key": send_params.s3_key,
            },
        )
        try:

            lock_name = send_params.send_lock_name()

            self._acquire_lock(lock_name, execution_id)

        except LockExists as e:
            self.response = return_failure(
                self.log_object,
                int(HTTPStatus.TOO_MANY_REQUESTS),
                "MESHSEND0003",
                send_params.sender,
                message=str(e),
            )
            return

        self.log_object.write_log(
            "MESHSEND0004",
            None,
            {
                "src_mailbox": send_params.sender,
                "dest_mailbox": send_params.recipient,
                "workflow_id": send_params.workflow_id,
                "bucket": bucket,
                "file": key,
                "file_size": human_readable_bytes(send_params.file_size),
                "chunks": send_params.total_chunks,
                "chunk_size": human_readable_bytes(self.config.chunk_size),
            },
        )

        # todo: in v3 send_params can replace most of these params but keep in v2 to support in-flight step functions
        self.response = {
            "statusCode": int(HTTPStatus.OK),
            "headers": {"Content-Type": "application/json"},
            "body": {
                "internal_id": self.log_object.internal_id,
                "src_mailbox": send_params.sender,
                "dest_mailbox": send_params.recipient,
                "workflow_id": send_params.workflow_id,
                "bucket": bucket,
                "key": key,
                "chunked": send_params.chunked,
                "chunk_number": 1,
                "total_chunks": send_params.total_chunks,
                "chunk_size": self.config.chunk_size,
                "message_id": None,
                "current_byte_position": 0,
                "send_params": asdict(send_params),
                "lock_name": lock_name,
                "execution_id": execution_id,
            },
        }


app = MeshCheckSendParametersApplication()


def lambda_handler(event, context):
    """Standard lambda_handler"""
    return app.main(event, context)
