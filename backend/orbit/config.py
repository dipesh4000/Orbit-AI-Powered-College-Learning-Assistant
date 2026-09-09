from pathlib import Path
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = ""
    dataset_dir: Path = ROOT.parent.parent
    llm_provider: str = "anthropic"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = "https://api.anthropic.com/v1"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rag_threshold: float = 0.35
    cookie_secure: bool = False
    allowed_origin: str = "http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        origin = self.allowed_origin.rstrip("/")
        result = [origin]
        parsed = urlsplit(origin)
        if parsed.scheme in {"http", "https"} and parsed.hostname in {
            "localhost",
            "127.0.0.1",
        }:
            alias = "127.0.0.1" if parsed.hostname == "localhost" else "localhost"
            port = f":{parsed.port}" if parsed.port is not None else ""
            result.append(f"{parsed.scheme}://{alias}{port}")
        return result

    @field_validator("dataset_dir", mode="after")
    @classmethod
    def resolve_dataset_dir(cls, value: Path) -> Path:
        return (ROOT / value).resolve() if not value.is_absolute() else value


settings = Settings()
