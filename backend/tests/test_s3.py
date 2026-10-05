from unittest.mock import patch

import pytest
from pydantic import AnyHttpUrl, SecretStr

from documind.core.config import Settings
from documind.storage.s3 import create_s3_client


def test_uses_localstack_connection_settings() -> None:
    settings = Settings(
        s3_region="us-east-1",
        s3_endpoint_url=AnyHttpUrl("http://localhost:4566"),
        s3_access_key_id=SecretStr("test"),
        s3_secret_access_key=SecretStr("test"),
    )

    with patch("documind.storage.s3.boto3.client") as client_factory:
        client = create_s3_client(settings)

    client_factory.assert_called_once()
    assert client is client_factory.return_value

    arguments = client_factory.call_args.kwargs
    assert client_factory.call_args.args == ("s3",)
    assert arguments["region_name"] == "us-east-1"
    assert arguments["endpoint_url"] == "http://localhost:4566/"
    assert arguments["aws_access_key_id"] == "test"
    assert arguments["aws_secret_access_key"] == "test"

    configuration = arguments["config"]
    assert configuration.signature_version == "s3v4"
    assert configuration.s3 == {"addressing_style": "path"}
    assert configuration.retries == {
        "mode": "standard",
        "total_max_attempts": 3,
    }
    assert configuration.connect_timeout == 5
    assert configuration.read_timeout == 30


def test_allows_aws_endpoint_and_credential_lookup() -> None:
    settings = Settings(
        s3_region="ca-central-1",
        s3_endpoint_url=None,
        s3_access_key_id=None,
        s3_secret_access_key=None,
    )

    with patch("documind.storage.s3.boto3.client") as client_factory:
        create_s3_client(settings)

    client_factory.assert_called_once()

    arguments = client_factory.call_args.kwargs
    assert arguments["region_name"] == "ca-central-1"
    assert arguments["endpoint_url"] is None
    assert arguments["aws_access_key_id"] is None
    assert arguments["aws_secret_access_key"] is None


@pytest.mark.parametrize(
    ("access_key_id", "secret_access_key"),
    [
        (SecretStr("test"), None),
        (None, SecretStr("test")),
    ],
)
def test_rejects_incomplete_credentials(
    access_key_id: SecretStr | None, secret_access_key: SecretStr | None
) -> None:
    settings = Settings(
        s3_endpoint_url=AnyHttpUrl("http://localhost:4566"),
        s3_access_key_id=access_key_id,
        s3_secret_access_key=secret_access_key,
    )

    with patch("documind.storage.s3.boto3.client") as client_factory:
        with pytest.raises(
            ValueError,
            match="S3 access key ID and secret access key must be provided together",
        ):
            create_s3_client(settings)

    client_factory.assert_not_called()
