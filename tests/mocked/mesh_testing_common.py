"""Common methods and classes used for testing mesh client"""

import json
from typing import cast

import requests

SANDBOX_URL = "https://localhost:8700"

LOCAL_MAILBOXES = ["X26ABC1", "X26ABC2"]
MB = 1024 * 1024


FILE_CONTENT = "123456789012345678901234567890123"
KNOWN_INTERNAL_ID = "20210701225219765177_TESTER"
KNOWN_INTERNAL_ID1 = "20210701225219765177_TEST01"
KNOWN_MESSAGE_ID1 = "20210704225941465332_MESG01"
KNOWN_MESSAGE_ID2 = "20210705133616577537_MESG02"
KNOWN_MESSAGE_ID3 = "20210705134726725149_MESG03"
CONTEXT = {"aws_request_id": "TESTREQUEST"}


def was_value_logged(logs: str, log_reference: str, key: str, value: str):
    """Was a particular key-value pair logged for a log reference"""
    for log_line in _get_log_lines(logs):
        if f"logReference={log_reference} " not in log_line:
            continue

        if f"{key}={value}" in log_line:
            return True

    return False


def _get_log_lines(logs: str):
    return [log_line for log_line in logs.split("\n") if log_line]


def inject_expired_non_delivery_report(
    mailbox_id: str,
    workflow_id: str,
    subject: str,
    local_id: str,
    file_name: str,
    linked_message_id: str,
) -> str:
    mailbox_id = (mailbox_id or "").strip().upper()
    assert mailbox_id
    data = {
        "mailbox_id": mailbox_id,
        "code": "14",
        "description": "Message not collected by recipient after 5 days",
        "workflow_id": workflow_id,
        "subject": f"NDR: {subject}",
        "local_id": local_id,
        "status": "undeliverable",
        "file_name": file_name,
        "linked_message_id": linked_message_id,
    }

    res = requests.post(
        f"{SANDBOX_URL}/messageexchange/admin/report",
        data=json.dumps(data),
        verify=False,  # NOSONAR
    )
    res.raise_for_status()
    return cast(str, res.json()["message_id"])


def reset_sandbox_mailbox(mailbox_id: str):
    mailbox_id = (mailbox_id or "").strip().upper()
    assert mailbox_id
    res = requests.delete(
        f"{SANDBOX_URL}/messageexchange/admin/reset/{mailbox_id}",
        verify=False,
    )
    res.raise_for_status()
