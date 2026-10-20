"""models.py - the local models (tokenizer, embeddings, re-ranker), loaded in one place (Module 3 and 4.3).

ingest.py, index.py, retrieve.py and verify.py all get their models from here, so a model is
configured and cached exactly once.
"""
from functools import lru_cache

import config


@lru_cache(maxsize=1)
def get_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings
    # Normalised vectors + cosine distance: what bge-small was trained for (Module 3.1)
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL, encode_kwargs={"normalize_embeddings": True})


@lru_cache(maxsize=1)
def get_reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(config.RERANKER_MODEL)
