"""Tests for MeshMailbox class (mesh_client wrapper)"""

import re
from collections.abc import Generator
from uuid import uuid4

import pytest
from nhs_aws_helpers import secrets_client, ssm_client
from shared.common import get_params, strtobool


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
