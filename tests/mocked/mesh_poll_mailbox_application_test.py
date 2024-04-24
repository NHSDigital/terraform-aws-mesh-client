import json
from http import HTTPStatus

from nhs_aws_helpers import stepfunctions
from pytest_httpserver import HTTPServer

from .mesh_testing_common import (
    CONTEXT,
    KNOWN_MESSAGE_ID1,
    KNOWN_MESSAGE_ID2,
    KNOWN_MESSAGE_ID3,
    was_value_logged,
)


def test_mesh_poll_mailbox_happy_path(
    httpserver: HTTPServer, environment: str, get_messages_sfn_arn: str, capsys
):
    """Test the lambda"""

    # Mock response from MESH server
    httpserver.expect_request(
        "/messageexchange/MESH-TEST1/inbox",
        "GET",
    ).respond_with_data(
        json.dumps(
            {
                "messages": [
                    KNOWN_MESSAGE_ID1,
                    KNOWN_MESSAGE_ID2,
                    KNOWN_MESSAGE_ID3,
                ]
            }
        ),
    )

    mailbox_name = "MESH-TEST1"
    mock_input = {"mailbox": mailbox_name}

    stepfunctions().start_execution(
        stateMachineArn=get_messages_sfn_arn,
        input=json.dumps(mock_input),
    )
    from mesh_poll_mailbox_application import MeshPollMailboxApplication

    app = MeshPollMailboxApplication()

    response = app.main(event=mock_input, context=CONTEXT)

    assert response["statusCode"] == int(HTTPStatus.OK)
    # check 3 messages received
    assert response["body"]["message_count"] == 3
    # check first message format in message_list
    assert (
        response["body"]["message_list"][0]["body"]["message_id"] == KNOWN_MESSAGE_ID1
    )
    assert False is response["body"]["message_list"][0]["body"]["complete"]
    assert response["body"]["message_list"][0]["body"]["dest_mailbox"] == mailbox_name

    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "LAMBDA0001", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0002", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "LAMBDA0003", "Log_Level", "INFO")
    assert was_value_logged(logs.out, "MESHPOLL0001", "Log_Level", "INFO")


def test_mesh_poll_mailbox_singleton_check(
    httpserver: HTTPServer, environment: str, get_messages_sfn_arn: str, capsys
):
    """Test the lambda"""
    from mesh_poll_mailbox_application import MeshPollMailboxApplication

    app = MeshPollMailboxApplication()

    # Mock response from MESH server
    httpserver.expect_request(
        "/messageexchange/MESH-TEST1/inbox",
        method="GET",
    ).respond_with_data(
        json.dumps(
            {
                "messages": [
                    KNOWN_MESSAGE_ID1,
                    KNOWN_MESSAGE_ID2,
                    KNOWN_MESSAGE_ID3,
                ]
            }
        ),
    )

    mailbox_name = "MESH-TEST1"
    mock_input = {"mailbox": mailbox_name}

    stepfunctions().start_execution(
        stateMachineArn=get_messages_sfn_arn,
        input=json.dumps(mock_input),
    )
    stepfunctions().start_execution(
        stateMachineArn=get_messages_sfn_arn,
        input=json.dumps(mock_input),
    )
    stepfunctions().start_execution(
        stateMachineArn=get_messages_sfn_arn,
        input=json.dumps(mock_input),
    )

    response = app.main(event=mock_input, context=CONTEXT)

    assert response["statusCode"] == int(HTTPStatus.TOO_MANY_REQUESTS)
