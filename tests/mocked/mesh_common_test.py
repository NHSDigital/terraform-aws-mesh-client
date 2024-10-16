"""Tests for MeshMailbox class (mesh_client wrapper)"""

import re
from collections.abc import Generator
from uuid import uuid4

import pytest
from freezegun import freeze_time
from nhs_aws_helpers import secrets_client, ssm_client
from shared.common import (
    LockDetails,
    LockExists,
    LockReleaseDenied,
    acquire_lock,
    get_params,
    release_lock,
    strtobool,
)


def find_log_entries(logs: str, log_reference) -> Generator[dict[str, str], None, None]:
    for line in logs.split("\n"):
        if f"logReference={log_reference} " not in line:
            continue

        yield {
            k: v.strip("\"'")
            for k, v in (
                match.split("=", maxsplit=1)
                for match in re.findall(
                    r'.*?\s(\w+=(?:\'[^\']+\'|"[^"]+"|[^ ]+))', line
                )
            )
        }


def test_get_params_ssm_and_secrets(environment: str):
    """
    Test get_params will get both ssm variables and secrets
    when use_secrets_manager is true
    """
    secrets = secrets_client()
    ssm = ssm_client()

    env = uuid4().hex

    secrets.create_secret(
        Name=f"/{env}/mesh/MESH_CLIENT_KEY",
        Description=f"/{env}/mesh/MESH_CLIENT_KEY",
        SecretString="DummyKey1",
    )
    secrets.create_secret(
        Name=f"/{env}/mesh/MESH_CLIENT_KEY2",
        Description=f"/{env}/mesh/MESH_CLIENT_KEY2",
        SecretString="DummyKey2",
    )
    secrets.create_secret(
        Name=f"/{env}/foobar/FOOBAR_KEY1",
        Description=f"/{env}/foobar/FOOBAR_KEY1",
        SecretString="FoobarKey2",
    )
    ssm.put_parameter(
        Name=f"/{env}/mesh/MESH_CLIENT_KEY",
        Description=f"/{env}/mesh/MESH_CLIENT_KEY",
        Overwrite=True,
        Type="String",
        Value="AnotherDummyLey",
    )

    ssm.put_parameter(
        Name=f"/{env}/mesh/MESH_URL1",
        Description=f"/{env}/mesh/MESH_URL1",
        Overwrite=True,
        Type="String",
        Value="DummyUrl1",
    )
    ssm.put_parameter(
        Name=f"/{env}/mesh/MESH_URL2",
        Description=f"/{env}/mesh/MESH_URL2",
        Overwrite=True,
        Type="String",
        Value="DummyUrl2",
    )
    ssm.put_parameter(
        Name=f"/{env}/foobar/FOOBAR_URL",
        Description=f"/{env}/foobar/FOOBAR_URL",
        Overwrite=True,
        Type="String",
        Value="FoobarUrl1",
    )
    param_dict = get_params(
        {
            f"/{env}/mesh/MESH_URL1",
            f"/{env}/mesh/MESH_URL2",
            f"/{env}/mesh/MESH_CLIENT_KEY",
        },
        {
            f"/{env}/mesh/MESH_CLIENT_KEY",
            f"/{env}/mesh/MESH_CLIENT_KEY2",
        },
        ssm=ssm,
        secrets=secrets,
    )
    expected_params = {
        f"/{env}/mesh/MESH_URL1": "DummyUrl1",
        f"/{env}/mesh/MESH_URL2": "DummyUrl2",
        f"/{env}/mesh/MESH_CLIENT_KEY": "DummyKey1",
        f"/{env}/mesh/MESH_CLIENT_KEY2": "DummyKey2",
    }
    assert expected_params == param_dict


@pytest.mark.parametrize("input_val", ["True", "true", "1", "Yes", "Y", "t", "T"])
def test_strtobool_true(input_val):
    assert strtobool(input_val, False) is True


@pytest.mark.parametrize("input_val", ["False", "false", "0", "No", "N", "f", "F"])
def test_strtobool_false(input_val):
    assert strtobool(input_val, False) is False


@pytest.mark.parametrize("input_val", ["HELLO", True, [], "YESH", 3, None])
def test_strtobool_exception_raised(input_val):
    with pytest.raises(
        ValueError,
        match='Expected "yes", "true", "t", "y", "1", "no", "false", "f", "n", "0"',
    ):
        strtobool(input_val, True)


@pytest.mark.parametrize("input_val", ["HELLO", True, [], "YESH", 3, None])
def test_strtobool_exception_swallowed(input_val):
    assert strtobool(input_val, False) is None


@freeze_time("2024-10-01", as_kwarg="frozen_time")
def test_acquire_lock(ddb_client, mocked_lock_table, **kwargs):
    """
    Ensure that a lock can bq acquired with teh expected values, and that this lock cannot be re-acquired.
    """
    lock_name = "TESTLOCK1234"
    execution_id1 = uuid4().hex
    execution_id2 = uuid4().hex

    result = acquire_lock(ddb_client, lock_name, execution_id1)

    with pytest.raises(LockExists) as sfe:
        acquire_lock(ddb_client, lock_name, execution_id2)
    assert str(sfe.value) == f"Lock already exists for {lock_name}"

    assert result.LockName == lock_name
    assert result.LockOwner == execution_id1
    assert result.AcquiredTime == str(kwargs["frozen_time"].time_to_freeze)


@freeze_time("2024-10-01", as_kwarg="frozen_time")
def test_acquire_lock_multi(ddb_client, mocked_lock_table, **kwargs):
    """
    Ensure that a lock can be acquired with the expected values, and that this lock cannot be re-acquired.
    """
    lock_name1 = "TESTLOCK1234"
    lock_name2 = "TESTLOCK5678"
    execution_id = uuid4().hex

    result1 = acquire_lock(ddb_client, lock_name1, execution_id)
    result2 = acquire_lock(ddb_client, lock_name2, execution_id)

    assert result1.LockName == lock_name1
    assert result1.LockOwner == execution_id
    assert result1.AcquiredTime == str(kwargs["frozen_time"].time_to_freeze)
    assert result2.LockName == lock_name2
    assert result2.LockOwner == execution_id
    assert result2.AcquiredTime == str(kwargs["frozen_time"].time_to_freeze)


def test_release_lock(ddb_client, mocked_lock_table, create_lock_row):
    """
    Ensure that when more than one lock row exists, release_lock() deletes the correct row.
    """

    _ = create_lock_row()
    named_lock_row = create_lock_row()

    assert (
        ddb_client.describe_table(TableName=mocked_lock_table["TableName"])["Table"][
            "ItemCount"
        ]
        == 2
    )

    release_result = release_lock(
        ddb_client, named_lock_row.LockName, named_lock_row.LockOwner
    )

    assert (
        ddb_client.describe_table(TableName=mocked_lock_table["TableName"])["Table"][
            "ItemCount"
        ]
        == 1
    )

    assert release_result == named_lock_row


def test_release_lock_not_owned(ddb_client, mocked_lock_table, create_lock_row):
    """
    Ensure that we are denied when attempting to a release a lock which is owned by another execution id.
    """
    existing_lock_row: LockDetails = create_lock_row()

    assert (
        ddb_client.describe_table(TableName=mocked_lock_table["TableName"])["Table"][
            "ItemCount"
        ]
        == 1
    )

    with pytest.raises(LockReleaseDenied) as ex:
        release_lock(ddb_client, existing_lock_row.LockName, uuid4().hex)

    assert ex.value.lock_name == existing_lock_row.LockName
    assert ex.value.lock_owner == existing_lock_row.LockOwner

    assert (
        ddb_client.describe_table(TableName=mocked_lock_table["TableName"])["Table"][
            "ItemCount"
        ]
        == 1
    )
