"""Runtime configuration.

Every provider credential is read from the environment and never logged. The
limits are not decoration: unbounded uploads and unbounded job time are how a
media product turns into an unbounded bill.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: str = Field(default="development")

    database_url: str = Field(
        default="postgresql+psycopg://preflight:preflight@localhost:5432/preflight"
    )

    parallel_api_key: str = Field(default="")
    google_cloud_project: str = Field(default="")
    google_cloud_location: str = Field(default="us-central1")
    gcs_bucket: str = Field(default="")
    vertex_model: str = Field(default="gemini-2.5-pro")
    firebase_project_id: str = Field(default="")

    max_upload_bytes: int = Field(default=2 * 1024 * 1024 * 1024)
    max_job_seconds: int = Field(default=900)
    signed_url_ttl_seconds: int = Field(default=900)
    delivery_token_ttl_hours: int = Field(default=168)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def missing_for_full_operation(self) -> list[str]:
        """Which providers are not configured yet.

        Reported by the readiness probe so a half-configured deployment says so
        plainly instead of failing later with an opaque provider error.
        """
        required = {
            "PARALLEL_API_KEY": self.parallel_api_key,
            "GOOGLE_CLOUD_PROJECT": self.google_cloud_project,
            "GCS_BUCKET": self.gcs_bucket,
            "FIREBASE_PROJECT_ID": self.firebase_project_id,
        }
        return sorted(name for name, value in required.items() if not value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
