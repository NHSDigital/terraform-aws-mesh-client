import os
from dataclasses import dataclass
from math import ceil
from typing import Any
from urllib.parse import unquote_plus

from mesh_client import optional_header_map
from mypy_boto3_s3.service_resource import Object
from mypy_boto3_ssm import SSMClient
from nhs_aws_helpers import ssm_client

from shared.common import convert_params_to_dict, strtobool
from shared.config import EnvConfig

_MESH_SEND_KWARGS = {
    "recipient",
    "total_chunks",
    "compress",
    *optional_header_map().keys(),
}


@dataclass
class SendParameters:
    s3_bucket: str
    s3_key: str
    sender: str
    recipient: str
    workflow_id: str | None = None
    filename: str | None = None
    file_size: int = 0
    content_type: str = "application/octet-stream"
    content_encoding: str = ""
    compress: bool | None = None
    compressed: bool | None = None
    encrypted: bool | None = None
    checksum: str | None = None
    local_id: str | None = None
    subject: str | None = None
    partner_id: str | None = None
    chunked: bool = False
    total_chunks: int = 1

    def to_client_kwargs(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in (
                ("recipient", self.recipient),
                ("total_chunks", self.total_chunks),
                ("compress", self.compress),
                ("workflow_id", self.workflow_id),
                ("filename", self.filename),
                ("local_id", self.local_id),
                ("subject", self.subject),
                ("encrypted", self.encrypted),
                ("compressed", self.compressed),
                ("checksum", self.checksum),
                ("partner_id", self.partner_id),
                ("content_type", self.content_type),
            )
            if v is not None and k in _MESH_SEND_KWARGS
        }

    def send_lock_name(self) -> str:
        return f"SendLock_{self.s3_bucket}_{self.s3_key}"


def get_send_parameters_from_mapping(
    s3_object: Object, config: EnvConfig, ssm: SSMClient | None = None
) -> SendParameters:
    bucket = s3_object.bucket_name
    key = s3_object.key
    folder = os.path.dirname(key)
    if len(folder) > 0:
        folder += "/"

    path = f"/{config.environment}/mesh/mapping/{bucket}/{folder}"
    ssm = ssm or ssm_client()
    mailbox_mapping_params = ssm.get_parameters_by_path(
        Path=path,
        Recursive=False,
        WithDecryption=True,
    )
    mailbox_mapping = convert_params_to_dict(
        mailbox_mapping_params.get("Parameters", {})
    )

    sender = mailbox_mapping["src_mailbox"]
    recipient = mailbox_mapping["dest_mailbox"]
    workflow_id = mailbox_mapping["workflow_id"]

    return SendParameters(
        s3_bucket=s3_object.bucket_name,
        s3_key=s3_object.key,
        sender=sender,
        recipient=recipient,
        workflow_id=workflow_id,
    )


def get_send_parameters(
    s3_object: Object, config: EnvConfig, ssm: SSMClient | None = None
) -> SendParameters:
    metadata = {k.lower(): unquote_plus(v) for k, v in s3_object.metadata.items()}

    params = (
        get_send_parameters_from_mapping(s3_object=s3_object, config=config, ssm=ssm)
        if not metadata or "mex-from" not in metadata
        else SendParameters(
            s3_bucket=s3_object.bucket_name,
            s3_key=s3_object.key,
            sender=metadata["mex-from"],
            recipient=metadata["mex-to"],
            workflow_id=metadata.get("mex-workflowid"),
        )
    )

    params.filename = metadata.get("mex-filename")
    if not params.filename and config.use_s3_key_for_mex_filename:
        # not recommended default behaviour as s3 key could be sensitive
        params.filename = os.path.basename(s3_object.key)

    params.file_size = s3_object.content_length
    params.content_type = s3_object.content_type
    params.content_encoding = s3_object.content_encoding

    params.chunked, params.total_chunks = calculate_chunks(
        params.file_size, config.chunk_size
    )

    if "mex-content-compressed" in metadata:
        params.compressed = bool(strtobool(metadata["mex-content-compressed"]))

    if "mex-content-encrypted" in metadata:
        params.encrypted = bool(strtobool(metadata["mex-content-encrypted"]))

    if config.never_compress or params.compressed:
        params.compress = False
    else:
        if params.file_size >= config.compress_threshold:
            params.compress = True

        encoding = params.content_encoding or ""
        if encoding:
            # don't compress if it's already compressed at the file level
            params.compress = False

        # per file instruction overrides defaults
        if "mex-content-compress" in metadata:
            params.compress = bool(strtobool(metadata["mex-content-compress"]))

    params.checksum = metadata.get("mex-content-checksum")
    params.local_id = metadata.get("mex-localid")
    params.subject = metadata.get("mex-subject")
    params.partner_id = metadata.get("mex-partnerid")

    return params


def calculate_chunks(file_size, chunk_size) -> tuple[bool, int]:
    """Helper for number of chunks"""
    chunks = ceil(file_size / chunk_size)
    do_chunking = bool(chunks > 1)
    return do_chunking, chunks
