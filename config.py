"""config.py - every setting lives here (Capstone R7).

Values come from the environment (.env file) and fall back to the defaults below,
so the project also runs with no .env at all. Other scripts import from this file.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")        # silently does nothing if the file does not exist


def _str(name, default):
    return os.environ.get(name, default)


def _int(name, default):
    return int(os.environ.get(name, default))


def _float(name, default):
    return float(os.environ.get(name, default))


def _bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# Paths (fixed, not env-controlled)
DOCS_DIR = ROOT / "documents"
CATALOG_PATH = ROOT / "catalog.csv"
TEST_SET_PATH = ROOT / "test_questions.json"
CHUNKS_PREVIEW_PATH = ROOT / "chunks_preview.txt"
INDEX_DIR = ROOT / "chroma_index"
EVAL_DIR = ROOT / "eval_results"
LOG_DIR = ROOT / "logs"

# Ingestion (Module 2): sizes are in embedding-model tokens
CHUNK_SIZE = _int("CHUNK_SIZE", 400)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 60)              # 15%

# Embeddings and index (Module 3)
EMBEDDING_MODEL = _str("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
COLLECTION_NAME = _str("COLLECTION_NAME", "kitewing")
DISTANCE = "cosine"                                    # fixed: what bge was trained for

# Retrieval (Module 4)
RETRIEVAL_MODE = _str("RETRIEVAL_MODE", "hybrid")      # semantic | keyword | hybrid
USE_RERANKER = _bool("USE_RERANKER", True)
RERANKER_MODEL = _str("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-12-v2")
CANDIDATES = _int("CANDIDATES", 20)
TOP_K = _int("TOP_K", 4)

# Generation (Module 5)
OLLAMA_URL = _str("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = _str("LLM_MODEL", "llama3.1:8b")
JUDGE_MODEL = _str("JUDGE_MODEL", "llama3.1:8b")
CONFIDENCE_THRESHOLD = _float("CONFIDENCE_THRESHOLD", 0.0)   # placeholder: calibrate in Phase 6

# Roles and regions (Module 6.1)
ROLES = ("employee", "hr")
REGIONS = ("US", "UK")