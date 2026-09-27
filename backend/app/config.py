from pathlib import Path
from urllib.parse import quote

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: Path = Path(__file__).resolve().parents[1] / "data" / "app.sqlite3"
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "procurement-processing"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_database: int = 0
    redis_password: SecretStr | None = None

    openai_api_key: str | None = None
    openai_extraction_model: str = "gpt-5.1"
    typesafe_api_key: str | None = Field(default=None, validation_alias=AliasChoices("TYPESAFE_API_KEY", "JEV_API_KEY"))
    typesafe_model: str = "jev-latest"
    typesafe_timeout_seconds: float = 10.0

    @property
    def redis_url(self) -> str:
        """Build the client URL without exposing the password as a configuration value."""
        password = self.redis_password.get_secret_value() if self.redis_password else None
        credentials = f":{quote(password, safe='')}@" if password else ""
        return f"redis://{credentials}{self.redis_host}:{self.redis_port}/{self.redis_database}"


settings = Settings()