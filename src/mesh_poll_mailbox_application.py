from http import HTTPStatus
from typing import Any

from aws_lambda_powertools.shared.functions import strtobool
from requests import HTTPError
from shared.application import MESHLambdaApplication
from shared.common import SingletonCheckFailure, return_failure, singleton_check


class HandshakeFailure(Exception):
    """Handshake failed"""

    def __init__(self, msg=None):
        super().__init__()
        self.msg = msg


class MeshPollMailboxApplication(MESHLambdaApplication):
    """
    MESH API Lambda for sending a message
    """

    def __init__(self, additional_log_config=None, load_ssm_params=False):
        """
        Init variables
        """
        super().__init__(additional_log_config, load_ssm_params)

        self.handshake: bool = False
        self.response: dict[str, Any] = {}

    def initialise(self):
        # initialise
        self.mailbox_id = self.event["mailbox"]
        self.handshake = bool(strtobool(self.event.get("handshake", "false")))
        self.response = {}

    def start(self):
        # in case of crash
        self.response = {"statusCode": int(HTTPStatus.INTERNAL_SERVER_ERROR)}

        if self.handshake:
            with self:
                self.perform_handshake()
                # 204 No Content is raised so the step function
                # ends without looking for messages
                self.response = {"statusCode": int(HTTPStatus.NO_CONTENT), "body": {}}
                return

        try:
            singleton_check(
                self.config.get_messages_step_function_arn,
                self.is_same_mailbox_check,
                self.sfn,
            )

        except SingletonCheckFailure as e:
            self.response = return_failure(
                self.log_object,
                int(HTTPStatus.TOO_MANY_REQUESTS),
                "MESHPOLL0002",
                self.mailbox_id,
                message=e.msg,
            )
            return

        with self:
            message_list = self.list_messages()

        message_count = len(message_list)

        if message_count == 0:
            # return 204 to keep state transitions to minimum if no messages
            self.response = {"statusCode": int(HTTPStatus.NO_CONTENT), "body": {}}
            return

        output_list = [
            {
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "complete": False,
                    "internal_id": self.log_object.internal_id,
                    "message_id": message,
                    "dest_mailbox": self.mailbox_id,
                },
            }
            for message in message_list
        ]

        self.log_object.write_log(
            "MESHPOLL0001",
            None,
            {
                "mailbox": self.mailbox_id,
                "message_count": message_count,
            },
        )

        # to set response for the lambda
        self.response = {
            "statusCode": int(HTTPStatus.OK),
            "headers": {"Content-Type": "application/json"},
            "body": {
                "internal_id": self.log_object.internal_id,
                "message_count": message_count,
                "message_list": output_list,
            },
            # Parameters for a follow-up iteration through the messages in this execution
            "mailbox": self.mailbox_id,
            "handshake": "false",  # No need to handshake again for this execution
        }

    def perform_handshake(self) -> int:
        """
        Do an authenticated handshake with the MESH server
        """

        try:
            self.mesh_client.handshake()
        except HTTPError as ex:
            self.log_object.write_log(
                "MESHMBOX0004",
                None,
                {"mailbox": self.mailbox_id, "http_status": ex.response.status_code},
            )
            raise HandshakeFailure from ex

        self.log_object.write_log(
            "MESHMBOX0004", None, {"mailbox": self.mailbox_id, "http_status": 200}
        )

        return 200

    def list_messages(self) -> list[str]:
        """Return a list of messages in the mailbox in the form:
        [
            '20220610195418651944_2202CC',
            '20220613142621549393_6430C9'
        ]
        """

        message_ids = self.mesh_client.list_messages(
            max_results=self.config.get_messages_page_limit
        )
        self.log_object.write_log(
            "MESHMBOX0005",
            None,
            {
                "mailbox": self.mailbox_id,
                "message_count": len(message_ids),
            },
        )
        return message_ids


# create instance of class in global space
# this ensures initial setup of logging/config is only done on cold start
app = MeshPollMailboxApplication()


def lambda_handler(event, context):
    """Standard lambda_handler"""
    return app.main(event, context)
