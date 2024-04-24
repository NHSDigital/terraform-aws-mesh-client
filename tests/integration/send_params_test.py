import gzip
from urllib.parse import quote_plus
from uuid import uuid4

from mypy_boto3_s3.service_resource import Bucket
from mypy_boto3_ssm import SSMClient
from shared.config import EnvConfig
from shared.send_parameters import get_send_parameters

from integration.test_helpers import temp_mapping_for_s3_object


def test_get_send_params_from_ssm_mapping(local_mesh_bucket: Bucket, ssm: SSMClient):
    env = uuid4().hex
    sender = uuid4().hex[:8].upper()
    recipient = uuid4().hex[:8].upper()
    workflow_id = f"{uuid4().hex[:8]} {uuid4().hex[:8]}"
    filename = f"{uuid4().hex}.dat"
    s3_object = local_mesh_bucket.Object(f"outbound_{sender}_to_{recipient}/{filename}")
    content = b"test"
    s3_object.put(Body=content, ContentType="text/plain")

    config = EnvConfig()
    config.environment = env

    with temp_mapping_for_s3_object(
        s3_object, sender, recipient, workflow_id, ssm, env=env
    ):
        params = get_send_parameters(s3_object=s3_object, config=config, ssm=ssm)

    assert params
    assert params.s3_bucket == s3_object.bucket_name
    assert params.s3_key == s3_object.key
    assert params.sender == sender
    assert params.recipient == recipient
    assert params.workflow_id == workflow_id
    assert params.filename is None
    assert params.content_type == "text/plain"
    assert not params.content_encoding
    assert params.file_size == len(content)
    assert not params.checksum
    assert not params.local_id
    assert not params.subject
    assert not params.partner_id
    assert params.compress is None
    assert params.compressed is None
    assert params.encrypted is None


def test_get_send_params_from_ssm_mapping_already_gzip_compressed(
    local_mesh_bucket: Bucket, ssm: SSMClient
):
    env = uuid4().hex
    sender = uuid4().hex[:8].upper()
    recipient = uuid4().hex[:8].upper()
    workflow_id = f"{uuid4().hex[:8]} {uuid4().hex[:8]}"
    filename = f"{uuid4().hex}.dat"
    s3_object = local_mesh_bucket.Object(f"outbound_{sender}_to_{recipient}/{filename}")
    content = gzip.compress(b"test")
    s3_object.put(Body=content, ContentType="text/plain", ContentEncoding="gzip")
    config = EnvConfig()
    config.environment = env

    with temp_mapping_for_s3_object(
        s3_object, sender, recipient, workflow_id, ssm, env=env
    ):
        params = get_send_parameters(s3_object=s3_object, config=config, ssm=ssm)

    assert params
    assert params.s3_bucket == s3_object.bucket_name
    assert params.s3_key == s3_object.key
    assert params.sender == sender
    assert params.recipient == recipient
    assert params.workflow_id == workflow_id
    assert params.filename is None
    assert params.content_type == "text/plain"
    assert params.content_encoding == "gzip"
    assert params.file_size == len(content)
    assert not params.checksum
    assert not params.local_id
    assert not params.subject
    assert not params.partner_id
    assert params.compress is False
    assert params.compressed is None
    assert params.encrypted is None


def test_get_send_params_from_ssm_mapping_already_deflate_compressed(
    local_mesh_bucket: Bucket, ssm: SSMClient
):
    env = uuid4().hex
    sender = uuid4().hex[:8].upper()
    recipient = uuid4().hex[:8].upper()
    workflow_id = f"{uuid4().hex[:8]} {uuid4().hex[:8]}"
    filename = f"{uuid4().hex}.dat"
    s3_object = local_mesh_bucket.Object(f"outbound_{sender}_to_{recipient}/{filename}")
    content = gzip.compress(b"test")
    s3_object.put(Body=content, ContentType="text/plain", ContentEncoding="deflate")
    config = EnvConfig()
    config.environment = env

    with temp_mapping_for_s3_object(
        s3_object, sender, recipient, workflow_id, ssm, env=env
    ):
        params = get_send_parameters(s3_object=s3_object, config=config, ssm=ssm)

    assert params
    assert params.s3_bucket == s3_object.bucket_name
    assert params.s3_key == s3_object.key
    assert params.sender == sender
    assert params.recipient == recipient
    assert params.workflow_id == workflow_id
    assert params.filename is None
    assert params.content_type == "text/plain"
    assert params.content_encoding == "deflate"
    assert params.file_size == len(content)
    assert not params.checksum
    assert not params.local_id
    assert not params.subject
    assert not params.partner_id
    assert params.compress is False
    assert params.compressed is None
    assert params.encrypted is None


def test_get_send_params_from_s3_metadata_minimal(
    local_mesh_bucket: Bucket, ssm: SSMClient
):
    env = uuid4().hex
    sender = uuid4().hex[:8].upper()
    recipient = uuid4().hex[:8].upper()
    workflow_id = f"{uuid4().hex[:8]} {uuid4().hex[:8]}"
    filename = f"{uuid4().hex}.dat"
    s3_object = local_mesh_bucket.Object(f"outbound_{sender}_to_{recipient}/{filename}")
    content = b"test"
    s3_object.put(
        Body=content,
        ContentType="text/plain",
        Metadata={
            "Mex-From": sender,
            "Mex-to": recipient,
            "Mex-WorkflowID": quote_plus(workflow_id),
        },
    )

    config = EnvConfig()
    config.environment = env

    params = get_send_parameters(s3_object=s3_object, config=config, ssm=ssm)

    assert params
    assert params.s3_bucket == s3_object.bucket_name
    assert params.s3_key == s3_object.key
    assert params.sender == sender
    assert params.recipient == recipient
    assert params.workflow_id == workflow_id
    assert params.filename is None
    assert params.content_type == "text/plain"
    assert not params.content_encoding
    assert params.file_size == len(content)
    assert not params.checksum
    assert not params.local_id
    assert not params.subject
    assert not params.partner_id
    assert params.compress is None
    assert params.compressed is None
    assert params.encrypted is None


def test_get_send_params_from_s3_metadata_full(
    local_mesh_bucket: Bucket, ssm: SSMClient
):
    env = uuid4().hex
    sender = uuid4().hex[:8].upper()
    recipient = uuid4().hex[:8].upper()
    workflow_id = f"{uuid4().hex[:8]} {uuid4().hex[:8]}"
    filename = f"{uuid4().hex}.dat"
    s3_object = local_mesh_bucket.Object(f"outbound_{sender}_to_{recipient}/{filename}")
    content = b"test"
    override_filename = "ooo/&*..txt"
    checksum = uuid4().hex
    local_id = uuid4().hex
    subject = uuid4().hex
    partner_id = uuid4().hex
    s3_object.put(
        Body=content,
        ContentType="text/plain",
        Metadata={
            "Mex-from": sender,
            "Mex-to": recipient,
            "Mex-workflowid": quote_plus(workflow_id),
            "Mex-filename": quote_plus(override_filename),
            "Mex-content-compress": "Y",
            "Mex-content-compressed": "N",
            "Mex-content-encrypted": "Y",
            "mex-content-checksum": checksum,
            "Mex-LocalID": local_id,
            "Mex-Subject": subject,
            "Mex-PartnerID": partner_id,
        },
    )

    config = EnvConfig()
    config.environment = env

    params = get_send_parameters(s3_object=s3_object, config=config, ssm=ssm)

    assert params
    assert params.s3_bucket == s3_object.bucket_name
    assert params.s3_key == s3_object.key
    assert params.sender == sender
    assert params.recipient == recipient
    assert params.workflow_id == workflow_id
    assert params.filename == override_filename
    assert params.content_type == "text/plain"
    assert not params.content_encoding
    assert params.file_size == len(content)
    assert params.checksum == checksum
    assert params.local_id == local_id
    assert params.subject == subject
    assert params.partner_id == partner_id
    assert params.compress is True
    assert params.compressed is False
    assert params.encrypted is True


def test_get_send_params_from_s3_use_s3_key_filename(
    local_mesh_bucket: Bucket, ssm: SSMClient
):
    env = uuid4().hex
    sender = uuid4().hex[:8].upper()
    recipient = uuid4().hex[:8].upper()
    workflow_id = f"{uuid4().hex[:8]} {uuid4().hex[:8]}"
    filename = f"{uuid4().hex}.dat"
    s3_object = local_mesh_bucket.Object(f"outbound_{sender}_to_{recipient}/{filename}")
    content = b"test"
    local_id = uuid4().hex
    s3_object.put(
        Body=content,
        ContentType="text/plain",
        Metadata={
            "Mex-from": sender,
            "Mex-to": recipient,
            "Mex-workflowid": quote_plus(workflow_id),
            "Mex-LocalID": local_id,
        },
    )

    config = EnvConfig()
    config.environment = env
    config.use_s3_key_for_mex_filename = True

    params = get_send_parameters(s3_object=s3_object, config=config, ssm=ssm)

    assert params
    assert params.s3_bucket == s3_object.bucket_name
    assert params.s3_key == s3_object.key
    assert params.sender == sender
    assert params.recipient == recipient
    assert params.workflow_id == workflow_id
    assert params.filename == filename
    assert params.content_type == "text/plain"
    assert not params.content_encoding
    assert params.file_size == len(content)

    assert params.local_id == local_id


def test_get_send_params_from_s3_use_s3_key_with_override_filename(
    local_mesh_bucket: Bucket, ssm: SSMClient
):
    env = uuid4().hex
    sender = uuid4().hex[:8].upper()
    recipient = uuid4().hex[:8].upper()
    workflow_id = f"{uuid4().hex[:8]} {uuid4().hex[:8]}"
    filename = f"{uuid4().hex}.dat"
    s3_object = local_mesh_bucket.Object(f"outbound_{sender}_to_{recipient}/{filename}")
    override_filename = "ooo/&*..txt"
    content = b"test"
    local_id = uuid4().hex
    s3_object.put(
        Body=content,
        ContentType="text/plain",
        Metadata={
            "Mex-from": sender,
            "Mex-to": recipient,
            "Mex-workflowid": quote_plus(workflow_id),
            "Mex-Filename": quote_plus(override_filename),
            "Mex-LocalID": local_id,
        },
    )

    config = EnvConfig()
    config.environment = env
    config.use_s3_key_for_mex_filename = True

    params = get_send_parameters(s3_object=s3_object, config=config, ssm=ssm)

    assert params
    assert params.s3_bucket == s3_object.bucket_name
    assert params.s3_key == s3_object.key
    assert params.sender == sender
    assert params.recipient == recipient
    assert params.workflow_id == workflow_id
    assert params.filename == override_filename
    assert params.content_type == "text/plain"
    assert not params.content_encoding
    assert params.file_size == len(content)

    assert params.local_id == local_id
