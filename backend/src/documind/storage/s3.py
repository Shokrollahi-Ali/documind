from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO, cast

import boto3
from botocore.config import Config
from fastapi import Request
from starlette.concurrency import run_in_threadpool

from documind.core.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


def create_s3_client(settings: Settings) -> S3Client:
    endpoint_url = None
    access_key_id = None
    secret_access_key = None

    if settings.s3_endpoint_url is not None:
        endpoint_url = str(settings.s3_endpoint_url)

    if settings.s3_access_key_id is not None:
        access_key_id = settings.s3_access_key_id.get_secret_value()

    if settings.s3_secret_access_key is not None:
        secret_access_key = settings.s3_secret_access_key.get_secret_value()

    if (access_key_id is None) != (secret_access_key is None):
        raise ValueError("S3 access key ID and secret access key must be provided together")

    client_config = Config(
        signature_version="s3v4",
        retries={"mode": "standard", "total_max_attempts": 3},
        connect_timeout=5,
        read_timeout=30,
        s3={"addressing_style": "path"},
    )

    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=client_config,
    )


async def get_s3_client(request: Request) -> S3Client:
    return cast("S3Client", request.app.state.s3_client)


async def upload_document_file(
    s3_client: S3Client, file: BinaryIO, bucket: str, storage_key: str, content_type: str
) -> None:
    await run_in_threadpool(
        s3_client.upload_fileobj,
        Fileobj=file,
        Bucket=bucket,
        Key=storage_key,
        ExtraArgs={"ContentType": content_type},
    )


async def delete_document_file(
    s3_client: S3Client,
    bucket: str,
    storage_key: str,
) -> None:
    await run_in_threadpool(s3_client.delete_object, Bucket=bucket, Key=storage_key)


async def download_document_file(
    s3_client: S3Client,
    file: BinaryIO,
    bucket: str,
    storage_key: str,
) -> None:
    await run_in_threadpool(
        s3_client.download_fileobj,
        Bucket=bucket,
        Key=storage_key,
        Fileobj=file,
    )
