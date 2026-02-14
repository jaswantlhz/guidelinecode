import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load env from agent/.env (shared key)
_env_path = Path(__file__).resolve().parent.parent / "agent" / ".env"
load_dotenv(_env_path)


class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    UNSTRUCTURED_API_KEY: str = os.getenv("UNSTRUCTURED_API", "")
    UNSTRUCTURED_URL: str = os.getenv("UNSTRUCTURED_URL", "https://platform.unstructuredapp.io/api/v1")

    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "cpic_rag")

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = BASE_DIR / "data"
    FAISS_INDEX_DIR: Path = DATA_DIR / "faiss_index"
    PHENOTYPE_CSV: Path = DATA_DIR / "phenotype_table.csv"
    PDF_DIR: Path = BASE_DIR / "pdfs"

    # Embedding model
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # LLM
    LLM_MODEL: str = "openai/gpt-oss-20b:free"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096

    class Config:
        env_file = str(_env_path)
        extra = "ignore"


settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
settings.PDF_DIR.mkdir(parents=True, exist_ok=True)
