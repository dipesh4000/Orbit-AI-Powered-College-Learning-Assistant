from pathlib import Path
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


settings = Settings()
