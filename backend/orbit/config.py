from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT.parent / ".env", extra="ignore")
    database_url: str = ""
    dataset_dir: Path = ROOT.parent.parent
    llm_provider: str = "anthropic"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = "https://api.anthropic.com/v1"
    nvidia_api_key: str = ""
    nvidia_model: str = "nvidia/nemotron-3-nano-30b-a3b"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_timeout_seconds: float = Field(default=30, gt=0, le=45)
    llm_fallback_cooldown_seconds: float = Field(default=300, ge=0)
    hf_token: str = ""
    hf_embedding_url: str = ""
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = Field(default=384, gt=0)
    embedding_query_prefix: str = (
        "Represent this sentence for searching relevant passages: "
    )
    embedding_timeout_seconds: float = Field(default=20, gt=0, le=30)
    rag_threshold: float = Field(default=0.6, ge=0, le=1)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    allowed_origin: str = "http://localhost:5173"

    @model_validator(mode="after")
    def validate_cookie_policy(self):
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        return self

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
