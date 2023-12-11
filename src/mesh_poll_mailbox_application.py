import os
from http import HTTPStatus
from typing import Any

from shared.common import MeshCommon, SingletonCheckFailure
from shared.mailbox import MeshMailbox
from spine_aws_common import LambdaApplication


class MeshPollMailboxApplication(LambdaApplication):
    """
    MESH API Lambda for sending a message
    """

    def __init__(self, additional_log_config=None, load_ssm_params=False):
        """
        Init variables
        """
        super().__init__(additional_log_config, load_ssm_params)
        self.mailbox: str = ""
        self.environment = os.environ.get("Environment", "default")
        self.get_messages_step_function_name = self.system_config.get(
            "GET_MESSAGES_STEP_FUNCTION_NAME", f"{self.environment}-get-messages"
        )
        self.handshake: str = "false"
        self.response: dict[str, Any] = {}

    def initialise(self):
        # initialise
        self.mailbox = self.event["mailbox"]
        self.handshake = self.event.get("handshake", "false")

    def start(self):
        # in case of crash
        self.response = {"statusCode": HTTPStatus.INTERNAL_SERVER_ERROR.value}

        with MeshMailbox(self.log_object, self.mailbox, self.environment) as mailbox:
            if self.handshake.lower() == "true":
                mailbox.handshake()
                # 204 No Content is raised so the step function
                # ends without looking for messages
                self.response = {"statusCode": HTTPStatus.NO_CONTENT.value, "body": {}}
                return

            try:
                MeshCommon.singleton_check(
                    self.mailbox,
                    self.get_messages_step_function_name,
                )
            except SingletonCheckFailure as e:
                self.response = MeshCommon.return_failure(
                    self.log_object,
                    HTTPStatus.TOO_MANY_REQUESTS.value,
                    "MESHPOLL0002",
                    self.mailbox,
                    message=e.msg,
                )
                return

            message_list = mailbox.list_messages()
            message_count = len(message_list)

            if message_count == 0:
                # return 204 to keep state transitions to minimum if no messages
                self.response = {"statusCode": HTTPStatus.NO_CONTENT.value, "body": {}}
                return

            output_list = [
                {
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "complete": False,
                        "internal_id": self.log_object.internal_id,
                        "message_id": message,
                        "dest_mailbox": self.mailbox,
                    },
                }
                for message in message_list
            ]

            self.log_object.write_log(
                "MESHPOLL0001",
                None,
                {
                    "mailbox": self.mailbox,
                    "message_count": message_count,
                },
            )

            # to set response for the lambda
            self.response = {
                "statusCode": HTTPStatus.OK.value,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "internal_id": self.log_object.internal_id,
                    "message_count": message_count,
                    "message_list": output_list,
                },
            }


# create instance of class in global space
# this ensures initial setup of logging/config is only done on cold start
app = MeshPollMailboxApplication()


def lambda_handler(event, context):
    """Standard lambda_handler"""
    return app.main(event, context)
