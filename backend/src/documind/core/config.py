from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_DATABASE_PASSWORD = "documind-local-only"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMIND_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: SecretStr = SecretStr(
        f"postgresql+psycopg://documind:{LOCAL_DATABASE_PASSWORD}@localhost:5432/documind"
    )
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    session_lifetime_seconds: int = Field(default=24 * 60 * 60, gt=0)
    session_cookie_name: str = Field(default="documind_session", min_length=1)
    s3_bucket: str = Field(default="documind-documents", min_length=1)
    s3_region: str = Field(default="us-east-1", min_length=1)
    s3_endpoint_url: AnyHttpUrl | None = None
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None

    @model_validator(mode="after")
    def reject_local_database_in_production(self) -> Self:
        if (
            self.environment == "production"
            and LOCAL_DATABASE_PASSWORD in self.database_url.get_secret_value()
        ):
            raise ValueError(
                "DOCUMIND_DATABASE_URL must be set to a production database "
                "when DOCUMIND_ENVIRONMENT is production"
            )
        return self
