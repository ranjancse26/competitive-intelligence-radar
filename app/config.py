import json
from pathlib import Path
from typing import Optional, List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    searchapi_api_key: str = ""
    searchapi_base_url: str = "https://www.searchapi.io/api/v1/search"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    search_num: int
    signal_keywords_path: Optional[str] = None

    # Default radar request values (sourced from config/defaults.json)
    default_competitors: List[str] = []
    default_keywords: List[str] = []
    default_days_back: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def _load_defaults() -> dict:
    """Load default radar values from the config/defaults.json file."""
    defaults_path = Path(__file__).resolve().parent.parent / "config" / "defaults.json"
    try:
        with open(defaults_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_defaults = _load_defaults()

settings = Settings(
    default_competitors=_defaults.get("default_competitors", []),
    default_keywords=_defaults.get("default_keywords", []),
    default_days_back=_defaults.get("default_days_back", 7),
)