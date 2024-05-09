import json
from http import HTTPStatus
from uuid import uuid4

from mesh_client import MeshClient
from nhs_aws_helpers import stepfunctions

from .mesh_testing_common import (
    CONTEXT,
    was_value_logged,
)


def test_mesh_poll_mailbox_happy_path(
    mesh_client_one: MeshClient,
    mesh_client_two: MeshClient,
    environment: str,
    get_messages_sfn_arn: str,
    capsys,
):
    num_messages = 3
    message_ids = [
        mesh_client_two.send_message(
            recipient=mesh_client_one._mailbox,
            workflow_id=uuid4().hex,
            data=f"Hello {i}".encode(),
        )
        for i in range(num_messages)
    ]

    mock_input = {"mailbox": mesh_client_one._mailbox}

    stepfunctions().start_execution(
        stateMachineArn=get_messages_sfn_arn,
        input=json.dumps(mock_input),
    )
    from mesh_poll_mailbox_application import MeshPollMailboxApplication

    app = MeshPollMailboxApplication()

    response = app.main(event=mock_input, context=CONTEXT)

    assert response["statusCode"] == int(HTTPStatus.OK)
    # check 3 messages received
    assert response["body"]["message_count"] == num_messages

    # check first message format in message_list
    assert {
        json.dumps(message["headers"]) for message in response["body"]["message_list"]
    } == {json.dumps({"Content-Type": "application/json"})}
    assert {
        message["body"]["complete"] for message in response["body"]["message_list"]
    } == {False}
    assert (
        len(
            {
                message["body"]["internal_id"]
                for message in response["body"]["message_list"]
            }
        )
        == 1
    )
    assert {
        message["body"]["dest_mailbox"] for message in response["body"]["message_list"]
    } == {mesh_client_one._mailbox}
    assert [
        message["body"]["message_id"] for message in response["body"]["message_list"]
    ] == message_ids

    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "LAMBDA0001", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0002", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHPOLL0001", "Log_Level", "INFO")


def test_mesh_poll_mailbox_singleton_check(
    environment: str, get_messages_sfn_arn: str, capsys
):
    from mesh_poll_mailbox_application import MeshPollMailboxApplication

    app = MeshPollMailboxApplication()

    mock_input = {"mailbox": uuid4().hex}

    stepfunctions().start_execution(
        stateMachineArn=get_messages_sfn_arn,
        input=json.dumps(mock_input),
    )
    # Have to run a second execution as the app.main() below doesn't actually create one
    # so the singleton check would just see the one above and think that it is itself.
    stepfunctions().start_execution(
        stateMachineArn=get_messages_sfn_arn,
        input=json.dumps(mock_input),
    )

    response = app.main(event=mock_input, context=CONTEXT)

    assert response["statusCode"] == int(HTTPStatus.TOO_MANY_REQUESTS)
