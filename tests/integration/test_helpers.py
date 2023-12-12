from __future__ import annotations

import base64
import json
import math
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from json import JSONDecodeError
from time import sleep, time
from typing import cast

import requests
from botocore.exceptions import ClientError
from mypy_boto3_lambda.type_defs import InvocationResponseTypeDef
from mypy_boto3_logs.type_defs import LogStreamTypeDef, OutputLogEventTypeDef
from mypy_boto3_stepfunctions import SFNClient
from mypy_boto3_stepfunctions.type_defs import DescribeExecutionOutputTypeDef
from nhs_aws_helpers import cloudwatchlogs_client, stepfunctions


def try_parse_json(message: str) -> dict | None:
    try:
        return cast(dict, json.loads(message))
    except JSONDecodeError:
        return None


def parse_kv_log(line: str) -> dict[str, str]:
    return {
        k: v.strip("\"'")
        for k, v in (match.split("=", maxsplit=1) for match in kv_log_re.findall(line))
    }


def try_parse_log_line(line: str) -> dict[str, str] | None:
    if not line:
        return None

    parsed = try_parse_json(line)
    if parsed:
        return parsed

    parsed = parse_kv_log(line)
    if parsed:
        return parsed

    return None


def lambda_log_lines(res: InvocationResponseTypeDef) -> list[str]:
    logs = base64.b64decode(res["LogResult"]).decode().strip().split("\n")
    return logs


def useful_lambda_logs(res: InvocationResponseTypeDef) -> list[str]:
    logs = lambda_log_lines(res)
    return [
        line
        for line in logs
        if line
        and not line.startswith("START ")
        and not line.startswith("END ")
        and not line.startswith("REPORT ")
        if line
    ]


kv_log_re = re.compile(r'(?:\s|^)(\w+=(?:\'[^\']+\'|"[^"]+"|[^ ]+))')


def parse_lambda_logs(
    res: InvocationResponseTypeDef, predicate: Callable[[dict], bool] | None = None
) -> list[dict]:
    useful_logs = useful_lambda_logs(res)

    return [
        log
        for log in (try_parse_log_line(line) for line in useful_logs)
        if log and (predicate is None or predicate(log))
    ]


def sync_lambda_invocation_successful(
    response: InvocationResponseTypeDef,
) -> tuple[str, list[str]]:
    assert response["StatusCode"] == 200

    raw_logs = ""
    logs = []

    if "LogResult" in response:
        logs = useful_lambda_logs(response)
        raw_logs = "\n".join(logs)

    function_error = response.get("FunctionError")
    if "Payload" not in response:
        raise AssertionError(f"lambda failed: {function_error}")

    payload = response["Payload"].read().decode()
    if not function_error:
        return payload, logs

    try:
        parsed = json.loads(payload)
        if "errorMessage" in payload:
            parsed["errorMessage"] = parsed["errorMessage"].split("\n")
        payload = json.dumps(parsed, indent=4)
    except JSONDecodeError:
        pass
    raise AssertionError(f"lambda failed: {function_error}\n{payload}\n{raw_logs}")


def sync_json_lambda_invocation_successful(
    response: InvocationResponseTypeDef,
    logs_predicate: Callable[[dict], bool] | None = None,
) -> tuple[dict, list[dict]]:
    raw_payload, _ = sync_lambda_invocation_successful(response)
    payload = json.loads(raw_payload)

    logs = parse_lambda_logs(response, predicate=logs_predicate)

    return payload, logs


def resource_path(path: str) -> str:
    path = (path or "").strip().strip("/")
    base_path = os.path.abspath(f"{os.path.dirname(__file__)}/../..")
    return f"{base_path}/{path}"


class CloudwatchLogsCapture:
    def __init__(
        self,
        log_group: str,
        start_timestamp: float | None = None,
    ):
        self._log_group = log_group
        self._start_timestamp = start_timestamp
        self._logs = cloudwatchlogs_client()
        self.reports: list[dict] = []
        self._last_split = time()

    def __enter__(self):
        self._start_timestamp = self._start_timestamp or time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            return False
        return True

    def _split(self) -> float:
        new_ts = time()
        split = new_ts - self._last_split
        self._last_split = new_ts
        return round(split, 6)

    def _get_log_streams(self, timeout: int = 10) -> list[LogStreamTypeDef]:
        end_wait = time() + timeout

        while True:
            try:
                response = self._logs.describe_log_streams(logGroupName=self._log_group)
                streams: list = response["logStreams"]

                while "nextToken" in response:
                    response = self._logs.describe_log_streams(
                        logGroupName=self._log_group,
                        nextToken=response["nextToken"],
                    )
                    streams.extend(response["logStreams"])
                return streams

            except ClientError as client_error:
                if (
                    client_error.response["Error"]["Code"]
                    != "ResourceNotFoundException"
                ):
                    raise client_error
                if time() > end_wait:
                    raise TimeoutError(
                        f"error waiting for streams for {self._log_group}"
                    ) from client_error
                sleep(0.1)
                continue

    def find_logs(self, split: float | None = None, parse_logs: bool = False):
        since = split or self._start_timestamp or 0

        since_timestamp = math.floor(since) * 1000

        self._split()

        logs: list[dict] = []
        response = self._logs.filter_log_events(
            logGroupName=self._log_group, startTime=since_timestamp
        )
        logs.extend(cast(list[dict], response["events"]))

        while "nextToken" in response:
            response = self._logs.filter_log_events(
                logGroupName=self._log_group,
                startTime=since_timestamp,
                nextToken=response["nextToken"],
            )
            logs.extend(cast(list[dict], response["events"]))

        self.reports.append({"filter_log_events": self._split(), "num_logs": len(logs)})

        if parse_logs:
            messages = [
                log.get("message", "").strip()
                for log in logs
                if log.get("message", "").startswith("{")
                or "logReference=" in log.get("message", "")
            ]
            parsed_logs = [try_parse_log_line(log) for log in messages]
            return parsed_logs

        return logs

    def wait_for_logs(
        self,
        min_results: int = 1,
        max_wait: int = 20,
        predicate: Callable[[dict], bool] | None = None,
        parse_logs: bool = False,
    ):
        end_wait = time() + max_wait

        while True:
            logs = self.find_logs(parse_logs=parse_logs)
            if not parse_logs:
                logs = [
                    jsonlog
                    for jsonlog in (try_parse_log_line(log["message"]) for log in logs)
                    if jsonlog
                ]

            if predicate:
                logs = [log for log in logs if predicate(log)]

            self.reports[-1]["filtered_logs"] = len(logs)

            if len(logs) >= min_results:
                return cast(list[dict], logs)

            if time() > end_wait:
                raise TimeoutError(
                    f"failed to match {min_results} json logs for log group {self._log_group} in {max_wait}s",
                    self.reports,
                )

            sleep(0.1)

    @staticmethod
    def match_events(
        events: Iterable[OutputLogEventTypeDef], match_re: re.Pattern[str]
    ) -> list[dict]:
        matched = []
        for event in events:
            match = match_re.match(event["message"])
            if not match:
                continue
            matched.append(dict(**event, match=match))

        return matched

    @staticmethod
    def find_lambda_invoke_errors(
        events: Iterable[OutputLogEventTypeDef],
    ) -> list[dict]:
        re_invoke_errors = re.compile(
            r"^(?P<timestamp>.*)\t(?P<request_id>.*)\tERROR\tInvoke Error \t(?P<detail>.*)$"
        )

        return CloudwatchLogsCapture.match_events(events, re_invoke_errors)


def wait_for_execution_outcome(
    execution_arn: str, sfn: SFNClient | None = None, timeout: float | int = 10
) -> tuple[dict | None, DescribeExecutionOutputTypeDef]:
    sfn = sfn or stepfunctions()
    start = time()
    end = start + timeout

    while True:
        describe = sfn.describe_execution(executionArn=execution_arn)
        if describe["status"] != "RUNNING":
            output_str = describe.get("output")
            if not output_str:
                return None, describe
            return try_parse_json(output_str), describe

        if time() > end:
            raise TimeoutError(f"timeout waiting for {execution_arn}", describe)

        sleep(0.2)


def wait_till_not_running(
    state_machine_arn: str, sfn: SFNClient | None = None, timeout: float | int = 10
):
    sfn = sfn or stepfunctions()
    start = time()
    end = start + timeout

    while True:
        list_result = sfn.list_executions(
            stateMachineArn=state_machine_arn, statusFilter="RUNNING"
        )
        # remove when merged: https://github.com/localstack/localstack/pull/9833
        executions = [
            ex for ex in list_result["executions"] if ex["status"] == "RUNNING"
        ]
        if not executions:
            return

        if time() > end:
            raise TimeoutError(f"timeout waiting for {state_machine_arn}", executions)

        sleep(0.2)


def reset_sandbox_mailbox(mailbox_id: str):
    mailbox_id = (mailbox_id or "").strip().upper()
    assert mailbox_id
    res = requests.delete(
        f"{os.environ['SANDBOX_URL']}/messageexchange/admin/reset/{mailbox_id}",
        verify=False,
    )
    res.raise_for_status()


@dataclass
class CreateReportRequest:
    mailbox_id: str  # recipient
    code: str  # error_code
    description: str  # error desc
    workflow_id: str
    subject: str | None = None
    local_id: str | None = None
    status: str = "undeliverable"  # report status (error/undeliverable)
    file_name: str | None = None
    linked_message_id: str | None = None


def put_sandbox_report(request: CreateReportRequest):
    res = requests.post(
        f"{os.environ['SANDBOX_URL']}/messageexchange/admin/report",
        json=asdict(request),
        verify=False,
    )
    res.raise_for_status()
    return res.json()
