import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load env from agent/.env (shared key)
_env_path = Path(__file__).resolve().parent.parent / "agent" / ".env"
load_dotenv(_env_path)


class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API", "")
    UNSTRUCTURED_API_KEY: str = os.getenv("UNSTRUCTURED_API_KEY") or os.getenv("UNSTRUCTURED_API", "")
    UNSTRUCTURED_URL: str = os.getenv("UNSTRUCTURED_URL", "https://platform.unstructuredapp.io/api/v1")
    UNSTRUCTURED_LEGACY_URL: str = os.getenv("UNSTRUCTURED_LEGACY_URL", "https://api.unstructuredapp.io/general/v0/general")

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
    # LLM
    LLM_MODEL: str = "nvidia/nemotron-3-nano-30b-a3b:free"
    LLM_FALLBACKS: list[str] = [
        "meta-llama/llama-3.2-3b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "liquid/lfm-2.5-1.2b-instruct:free",
        "stepfun/step-3.5-flash:free",
        "openrouter/free",
    ]
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
