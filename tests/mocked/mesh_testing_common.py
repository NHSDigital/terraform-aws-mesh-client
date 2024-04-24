"""Common methods and classes used for testing mesh client"""

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
