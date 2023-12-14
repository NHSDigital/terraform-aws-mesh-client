import os.path
from collections.abc import Generator
from contextlib import contextmanager
from time import time
from typing import Literal
from uuid import uuid4

import pytest
from mypy_boto3_s3.service_resource import Bucket
from mypy_boto3_secretsmanager import SecretsManagerClient
from mypy_boto3_ssm import SSMClient
from shared.application import (
    INBOUND_BUCKET,
    INBOUND_FOLDER,
    MAILBOX_PARAMS_CACHE_TIME,
    MAILBOX_PASSWORD,
    MESHLambdaApplication,
)
from shared.config import EnvConfig

from integration.test_helpers import temp_env_vars


@contextmanager
def setup_config(
    env: str,
    mesh_bucket: str,
    ssm: SSMClient,
    secrets: SecretsManagerClient,
    ssm_params: dict[str, str] | None = None,
    secret_values: dict[str, str] | None = None,
    **env_vars,
) -> Generator[EnvConfig, None, None]:
    all_env_vars = {
        "ENVIRONMENT": env,
        "USE_SECRETS_MANAGER": "false",
        "VERIFY_SSL": "true",
        "USE_SENDER_FILENAME": "false",
        "USE_LEGACY_INBOUND_LOCATION": "false",
        "MESH_BUCKET": mesh_bucket,
        "CA_CERT_CONFIG_KEY": f"/{env}/mesh/MESH_CA_CERT",
        "CLIENT_CERT_CONFIG_KEY": f"/{env}/mesh/MESH_CLIENT_CERT",
        "CLIENT_KEY_CONFIG_KEY": f"/{env}/mesh/MESH_CLIENT_KEY",
        "SHARED_KEY_CONFIG_KEY": f"/{env}/mesh/MESH_SHARED_KEY",
        "MAILBOXES_BASE_CONFIG_KEY": f"/{env}/mesh/mailboxes",
    }

    ssm_params = ssm_params or {}
    secret_values = secret_values or {}
    all_env_vars.update(env_vars)
    all_ssm_params = {
        f"/{env}/mesh/MESH_CA_CERT": "ca-cert",
        f"/{env}/mesh/MESH_CLIENT_CERT": "client-cert",
    }
    all_ssm_params.update(ssm_params)
    with temp_env_vars(**all_env_vars):
        for name, value in all_ssm_params.items():
            param_type: Literal["SecureString", "String"] = (
                "SecureString" if name.endswith("_KEY") else "String"
            )
            ssm.put_parameter(Name=name, Value=value, Type=param_type, Overwrite=True)

        for secret_id, value in secret_values.items():
            # this will fail if the secrets already exist (outside), so safe to delete below
            secrets.create_secret(Name=secret_id, SecretString=value)

        config = EnvConfig()
        yield config

        ssm.delete_parameters(Names=list(all_ssm_params.keys()))

        for secret_id in secret_values:
            secrets.delete_secret(SecretId=secret_id, ForceDeleteWithoutRecovery=True)


def test_mesh_application_config_defaults(
    ssm: SSMClient, secrets: SecretsManagerClient, temp_s3_bucket: Bucket
):
    env = uuid4().hex[:8].upper()
    mailbox = uuid4().hex[:8].upper()
    with setup_config(
        env=env, mesh_bucket=temp_s3_bucket.name, ssm=ssm, secrets=secrets
    ):
        app = MESHLambdaApplication()
        app.ensure_params(mailbox)
        assert app.config.environment == env
        assert app.config.verify_ssl
        assert app.verify == app.ca_cert_path
        assert not app.config.use_secrets_manager
        assert not app.config.use_legacy_inbound_location
        assert not app.config.use_sender_filename
        assert not app.shared_key
        with open(app.ca_cert_path, encoding="utf-8") as f:
            assert f.read() == "ca-cert"

        with open(app.client_cert_path, encoding="utf-8") as f:
            assert f.read() == "client-cert"

        assert not os.path.exists(app.client_key_path)

        assert app.mailbox_params[mailbox]
        assert not app.mailbox_params[mailbox]["params"]


def test_mesh_application_no_verify_ssl(
    ssm: SSMClient, secrets: SecretsManagerClient, temp_s3_bucket: Bucket
):
    env = uuid4().hex[:8].upper()
    mailbox = uuid4().hex[:8].upper()
    with setup_config(
        env=env,
        mesh_bucket=temp_s3_bucket.name,
        ssm=ssm,
        secrets=secrets,
        VERIFY_SSL="false",
    ):
        app = MESHLambdaApplication()
        app.ensure_params(mailbox)
        assert app.config.environment == env
        assert app.verify is False
        assert not app.config.verify_ssl
        assert not app.config.use_secrets_manager
        assert not app.config.use_legacy_inbound_location
        assert not app.config.use_sender_filename
        assert not app.shared_key

        assert not os.path.exists(app.ca_cert_path)
        assert not os.path.exists(app.client_key_path)

        assert app.mailbox_params[mailbox]
        assert not app.mailbox_params[mailbox]["params"]


@pytest.mark.parametrize(
    ("use_legacy_inbound_location", "expected_mailbox_params"),
    [
        (False, {MAILBOX_PASSWORD: "password-from-ssm"}),
        (
            True,
            {
                MAILBOX_PASSWORD: "password-from-ssm",
                INBOUND_BUCKET: "bucket-from-ssm",
                INBOUND_FOLDER: "folder-from-ssm",
            },
        ),
    ],
)
def test_mesh_application_ssm_when_both_exist(
    use_legacy_inbound_location: bool,
    expected_mailbox_params: dict[str, str],
    ssm: SSMClient,
    secrets: SecretsManagerClient,
    temp_s3_bucket: Bucket,
):
    env = uuid4().hex[:8].upper()
    mailbox = uuid4().hex[:8].upper()

    ssm_params = {
        f"/{env}/mesh/MESH_SHARED_KEY": "shared-key-from-ssm",
        f"/{env}/mesh/MESH_CLIENT_KEY": "client-key-from-ssm",
        f"/{env}/mesh/mailboxes/{mailbox}/{MAILBOX_PASSWORD}": "password-from-ssm",
        f"/{env}/mesh/mailboxes/{mailbox}/{INBOUND_BUCKET}": "bucket-from-ssm",
        f"/{env}/mesh/mailboxes/{mailbox}/{INBOUND_FOLDER}": "folder-from-ssm",
    }
    secret_values = {
        f"/{env}/mesh/MESH_SHARED_KEY": "shared-key-from-secrets",
        f"/{env}/mesh/MESH_CLIENT_KEY": "client-key-from-secrets",
        f"/{env}/mesh/mailboxes/{mailbox}/{MAILBOX_PASSWORD}": "password-from-secrets",
    }
    with setup_config(
        env=env,
        mesh_bucket=temp_s3_bucket.name,
        ssm_params=ssm_params,
        secret_values=secret_values,
        ssm=ssm,
        secrets=secrets,
        USE_LEGACY_INBOUND_LOCATION=str(use_legacy_inbound_location),
    ):
        app = MESHLambdaApplication()
        app.ensure_params(mailbox)
        assert app.config.environment == env
        assert app.config.verify_ssl
        assert not app.config.use_secrets_manager
        assert app.config.use_legacy_inbound_location == use_legacy_inbound_location
        assert not app.config.use_sender_filename
        assert app.shared_key == "shared-key-from-ssm"

        with open(app.ca_cert_path, encoding="utf-8") as f:
            assert f.read() == "ca-cert"

        with open(app.client_cert_path, encoding="utf-8") as f:
            assert f.read() == "client-cert"

        with open(app.client_key_path, encoding="utf-8") as f:
            assert f.read() == "client-key-from-ssm"

        assert app.mailbox_params[mailbox]
        assert app.mailbox_params[mailbox]["params"] == expected_mailbox_params


@pytest.mark.parametrize(
    ("use_legacy_inbound_location", "expected_mailbox_params"),
    [
        (False, {MAILBOX_PASSWORD: "password-from-secrets"}),
        (
            True,
            {
                MAILBOX_PASSWORD: "password-from-secrets",
                INBOUND_BUCKET: "bucket-from-ssm",
                INBOUND_FOLDER: "folder-from-ssm",
            },
        ),
    ],
)
def test_mesh_application_secrets_when_both_exist(
    use_legacy_inbound_location: bool,
    expected_mailbox_params: dict[str, str],
    ssm: SSMClient,
    secrets: SecretsManagerClient,
    temp_s3_bucket: Bucket,
):
    env = uuid4().hex[:8].upper()
    mailbox = uuid4().hex[:8].upper()

    ssm_params = {
        f"/{env}/mesh/MESH_SHARED_KEY": "shared-key-from-ssm",
        f"/{env}/mesh/MESH_CLIENT_KEY": "client-key-from-ssm",
        f"/{env}/mesh/mailboxes/{mailbox}/{MAILBOX_PASSWORD}": "password-from-ssm",
        f"/{env}/mesh/mailboxes/{mailbox}/{INBOUND_BUCKET}": "bucket-from-ssm",
        f"/{env}/mesh/mailboxes/{mailbox}/{INBOUND_FOLDER}": "folder-from-ssm",
    }
    secret_values = {
        f"/{env}/mesh/MESH_SHARED_KEY": "shared-key-from-secrets",
        f"/{env}/mesh/MESH_CLIENT_KEY": "client-key-from-secrets",
        f"/{env}/mesh/mailboxes/{mailbox}/{MAILBOX_PASSWORD}": "password-from-secrets",
    }
    with setup_config(
        env=env,
        mesh_bucket=temp_s3_bucket.name,
        ssm_params=ssm_params,
        secret_values=secret_values,
        ssm=ssm,
        secrets=secrets,
        USE_LEGACY_INBOUND_LOCATION=str(use_legacy_inbound_location),
        USE_SECRETS_MANAGER="true",
    ):
        app = MESHLambdaApplication()
        app.ensure_params(mailbox)
        assert app.config.environment == env
        assert app.config.verify_ssl
        assert app.config.use_secrets_manager
        assert app.config.use_legacy_inbound_location == use_legacy_inbound_location
        assert not app.config.use_sender_filename
        assert app.shared_key == "shared-key-from-secrets"

        with open(app.ca_cert_path, encoding="utf-8") as f:
            assert f.read() == "ca-cert"

        with open(app.client_cert_path, encoding="utf-8") as f:
            assert f.read() == "client-cert"

        with open(app.client_key_path, encoding="utf-8") as f:
            assert f.read() == "client-key-from-secrets"

        assert app.mailbox_params[mailbox]
        assert app.mailbox_params[mailbox]["params"] == expected_mailbox_params


def test_mesh_application_ssm_updated_when_expired(
    ssm: SSMClient, secrets: SecretsManagerClient, temp_s3_bucket: Bucket
):
    env = uuid4().hex[:8].upper()
    mailbox = uuid4().hex[:8].upper()

    ssm_params = {
        f"/{env}/mesh/MESH_SHARED_KEY": "shared-key-from-ssm",
        f"/{env}/mesh/MESH_CLIENT_KEY": "client-key-from-ssm",
        f"/{env}/mesh/mailboxes/{mailbox}/{MAILBOX_PASSWORD}": "password-from-ssm",
    }

    with setup_config(
        env=env,
        mesh_bucket=temp_s3_bucket.name,
        ssm_params=ssm_params,
        ssm=ssm,
        secrets=secrets,
    ):
        app = MESHLambdaApplication()
        app.ensure_params(mailbox)
        assert app.config.environment == env
        assert app.config.verify_ssl
        assert not app.config.use_secrets_manager
        assert not app.config.use_legacy_inbound_location
        assert not app.config.use_sender_filename
        assert app.shared_key == "shared-key-from-ssm"

        with open(app.ca_cert_path, encoding="utf-8") as f:
            assert f.read() == "ca-cert"

        with open(app.client_cert_path, encoding="utf-8") as f:
            assert f.read() == "client-cert"

        with open(app.client_key_path, encoding="utf-8") as f:
            assert f.read() == "client-key-from-ssm"

        assert app.mailbox_params[mailbox]
        assert app.mailbox_params[mailbox]["params"] == {
            MAILBOX_PASSWORD: "password-from-ssm"
        }

        ssm.put_parameter(
            Name=f"/{env}/mesh/mailboxes/{mailbox}/{MAILBOX_PASSWORD}",
            Value="updated",
            Type="SecureString",
            Overwrite=True,
        )
        ssm.put_parameter(
            Name=f"/{env}/mesh/MESH_SHARED_KEY",
            Value="updated",
            Type="SecureString",
            Overwrite=True,
        )
        ssm.put_parameter(
            Name=f"/{env}/mesh/MESH_CLIENT_KEY",
            Value="updated",
            Type="SecureString",
            Overwrite=True,
        )

        app.mailbox_params[mailbox]["retrieved"] = (
            time() - MAILBOX_PARAMS_CACHE_TIME - 1
        )

        app.ensure_params(mailbox)

        assert app.shared_key == "shared-key-from-ssm"
        with open(app.client_key_path, encoding="utf-8") as f:
            assert f.read() == "client-key-from-ssm"

        assert app.mailbox_params[mailbox]["params"] == {MAILBOX_PASSWORD: "updated"}
