from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMIND_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://documind:documind-local-only@localhost:5432/documind"
    )
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    s3_bucket: str = Field(default="documind-documents", min_length=1)
    s3_region: str = Field(default="us-east-1", min_length=1)
    s3_endpoint_url: AnyHttpUrl | None = None
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
