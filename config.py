"""config.py - every setting lives here (Capstone R7).

Values come from the environment (.env file) and fall back to the defaults below,
so the project also runs with no .env at all. Other scripts import from this file.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")        # silently does nothing if the file does not exist


def _str(name, default):
    return os.environ.get(name, default)


def _number(name, default, kind):
    """Read a numeric setting. A typo in .env ends with one clear line, not a stack trace."""
    raw = os.environ.get(name, default)
    try:
        return kind(raw)
    except ValueError:
        sys.exit(f"\nProblem: the setting {name} must be a number, but it is '{raw}'. Fix it in your .env file.")


def _int(name, default):
    return _number(name, default, int)


def _float(name, default):
    return _number(name, default, float)


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
NEAR_DUP_THRESHOLD = _float("NEAR_DUP_THRESHOLD", 0.6)   # report file pairs at least this similar

# Embeddings and index (Module 3)
EMBEDDING_MODEL = _str("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
COLLECTION_NAME = _str("COLLECTION_NAME", "kitewing")
DISTANCE = "cosine"                                    # fixed: what bge was trained for
EMBED_BATCH_SIZE = _int("EMBED_BATCH_SIZE", 32)
HNSW_MAX_NEIGHBORS = _int("HNSW_MAX_NEIGHBORS", 16)          # "m": edges per node
HNSW_EF_CONSTRUCTION = _int("HNSW_EF_CONSTRUCTION", 200)     # search depth while building

# Retrieval (Module 4)
RETRIEVAL_MODE = _str("RETRIEVAL_MODE", "hybrid")      # semantic | keyword | hybrid
USE_RERANKER = _bool("USE_RERANKER", True)
RERANKER_MODEL = _str("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-12-v2")
CANDIDATES = _int("CANDIDATES", 20)
TOP_K = _int("TOP_K", 4)

# Generation (Module 5)
# One switch for every model call: ollama (local, free, the default) or openai (optional, fast).
# LLM_MODEL and JUDGE_MODEL always hold the model for the ACTIVE provider, so no other file cares.
LLM_PROVIDER = _str("LLM_PROVIDER", "ollama").lower()
OLLAMA_URL = _str("OLLAMA_URL", "http://localhost:11434")

if LLM_PROVIDER == "openai":
    LLM_MODEL = _str("OPENAI_LLM_MODEL", "gpt-4o-mini")
    JUDGE_MODEL = _str("OPENAI_JUDGE_MODEL", LLM_MODEL)
else:
    LLM_MODEL = _str("LLM_MODEL", "llama3.2:3b")          # suits an 8 GB laptop; use llama3.1:8b with 16 GB or more
    JUDGE_MODEL = _str("JUDGE_MODEL", "llama3.2:3b")

CONFIDENCE_THRESHOLD = _float("CONFIDENCE_THRESHOLD", -6.9)   # calibrated from test_questions.json (generate.py --calibrate)
MAX_ANSWER_TOKENS = _int("MAX_ANSWER_TOKENS", 300)     # caps runaway replies from small models
FALLBACK_MESSAGE = _str(
    "FALLBACK_MESSAGE",
    "I don't have that information in the documents I can access. "
    "For HR questions, contact the People Team (people@kitewing.example); "
    "for IT questions, contact the IT Helpdesk (it-help@kitewing.example).")

# Roles and regions (Module 6.1)
ROLES = ("employee", "hr")
REGIONS = ("US", "UK")

# Every setting that changes an answer: logged with each answer and saved with each evaluation run (Module 6.5)
SETTING_NAMES = (
    "CHUNK_SIZE", "CHUNK_OVERLAP", "EMBEDDING_MODEL", "DISTANCE",
    "HNSW_MAX_NEIGHBORS", "HNSW_EF_CONSTRUCTION", "RETRIEVAL_MODE", "USE_RERANKER",
    "RERANKER_MODEL", "CANDIDATES", "TOP_K", "LLM_PROVIDER", "LLM_MODEL", "JUDGE_MODEL",
    "CONFIDENCE_THRESHOLD", "MAX_ANSWER_TOKENS",
)


def current_settings():
    return {name: globals()[name] for name in SETTING_NAMES}