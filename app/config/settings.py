from typing import List

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # API Keys
    GROQ_API_KEY: str = ""
    GROQ_API_KEYS: str = ""

    # Target markets
    APP_STORE_COUNTRIES: List[str] = ["US", "GB", "IN", "BR", "DE"]
    PLAY_STORE_COUNTRIES: List[str] = ["US", "GB", "IN", "BR", "DE"]

    # Database
    SQLITE_DB_PATH: str = "data/feedback.db"
    CHROMA_PERSIST_DIR: str = "data/chroma"

    # Model Config
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Collection & Classification Caps
    MAX_RECORDS_PER_SOURCE_PER_RUN: int = 200
    MAX_CLASSIFICATIONS_PER_RUN: int = 900
    MIN_PATTERN_SAMPLE: int = 10

    # Scheduler
    COLLECTION_HOUR: int = 0
    COLLECTION_MINUTE: int = 0

    # Clustering (Phase 4.5)
    MIN_CLUSTER_SIZE: int = 5
    MIN_SAMPLES: int = 3
    CLUSTER_FIELDS: List[str] = ["topic", "core_complaint", "behaviour_pattern", "unmet_need"]
    MAX_LABEL_SAMPLES: int = 20

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
