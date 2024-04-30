""" Testing Get File From S3 Function """

from nhs_aws_helpers import s3_resource

FILE_CONTENT = "123456789012345678901234567890123"
FILE_SIZE = len(FILE_CONTENT)

MEBIBYTE = 1024 * 1024
DEFAULT_BUFFER_SIZE = 20 * MEBIBYTE


def test_get_file_from_s3_with_parts(environment: str, mesh_s3_bucket: str):
    """
    Test _get_file_from_s3 getting an uncompressed large file
    """
    from mesh_send_message_chunk_application import MeshSendMessageChunkApplication

    app = MeshSendMessageChunkApplication()

    app.current_byte = 0

    app.s3_object = s3_resource().Object(
        mesh_s3_bucket, "MESH-TEST2/outbound/testfile.json"
    )
    app.config.crumb_size = 7
    app.config.chunk_size = app.s3_object.content_length * 2
    gen = app._get_chunk_from_s3()
    assert next(gen) == b"1234567"
    assert next(gen) == b"8901234"
    assert next(gen) == b"5678901"
    assert next(gen) == b"2345678"
    assert next(gen) == b"90123"


def test_get_file_from_s3_without_parts(environment: str, mesh_s3_bucket: str):
    """
    Test _get_file_from_s3 getting an uncompressed small file
    """
    from mesh_send_message_chunk_application import MeshSendMessageChunkApplication

    app = MeshSendMessageChunkApplication()

    app.current_byte = 0

    app.s3_object = s3_resource().Object(
        mesh_s3_bucket, "MESH-TEST2/outbound/testfile.json"
    )
    app.config.crumb_size = app.s3_object.content_length + 1
    app.config.chunk_size = app.s3_object.content_length * 2
    gen = app._get_chunk_from_s3()
    all_33_bytes = next(gen)
    assert all_33_bytes == b"123456789012345678901234567890123"
