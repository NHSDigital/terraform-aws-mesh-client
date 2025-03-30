import json
from http import HTTPStatus
from uuid import uuid4

from mesh_client import MeshClient
from nhs_aws_helpers import stepfunctions
from shared.common import LockExists

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
    mocked_lock_table,
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

    mock_input = {
        "EventDetail": {"mailbox": mesh_client_one._mailbox},
        "ExecutionId": "TEST12345",
    }

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


def test_mesh_poll_mailbox_lock_exists(
    monkeypatch, mesh_client_one, get_messages_sfn_arn
):
    mock_input = {
        "EventDetail": {"mailbox": mesh_client_one._mailbox},
        "ExecutionId": "TEST12345",
    }

    stepfunctions().start_execution(
        stateMachineArn=get_messages_sfn_arn,
        input=json.dumps(mock_input),
    )
    from mesh_poll_mailbox_application import MeshPollMailboxApplication

    app = MeshPollMailboxApplication()

    def no_lockie(_, __):
        raise LockExists("test", "test2", "test3")

    monkeypatch.setattr(app, "_acquire_lock", no_lockie)

    response = app.main(event=mock_input, context=CONTEXT)

    assert response["statusCode"] == 429
    assert response["body"]["error"] == "Lock already exists for test"
