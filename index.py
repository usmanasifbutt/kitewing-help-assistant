"""index.py - embed chunks and store them in a persistent Chroma index (Capstone R2, Module 3).

Each build goes into its own folder; the CURRENT file names the active one. A failed
rebuild therefore never touches the working index (safe rebuild).
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import config
import ingest

POINTER = config.INDEX_DIR / "CURRENT"
INFO_FILE = "index_info.json"


class IndexProblem(Exception):
    """A predictable index problem. The message tells the user what to do next."""


def get_embeddings():
    # Normalised vectors + cosine distance: what bge-small was trained for (Module 3.1)
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL,
                                 encode_kwargs={"normalize_embeddings": True})


def hnsw_config():
    return {"hnsw": {"space": config.DISTANCE,
                     "max_neighbors": config.HNSW_MAX_NEIGHBORS,
                     "ef_construction": config.HNSW_EF_CONSTRUCTION}}


# ---------------------------------------------------------------- build
def build_index():
    start = time.time()
    chunks, _ = ingest.ingest()
    ids = [c.metadata["chunk_id"] for c in chunks]
    if len(set(ids)) != len(ids):
        raise IndexProblem("Duplicate chunk IDs found. Check the doc_id values in catalog.csv.")

    config.INDEX_DIR.mkdir(exist_ok=True)
    version = "v" + datetime.now().strftime("%Y%m%d-%H%M%S")
    new_dir = config.INDEX_DIR / version
    try:
        store = Chroma(collection_name=config.COLLECTION_NAME,
                       embedding_function=get_embeddings(),
                       persist_directory=str(new_dir),
                       collection_configuration=hnsw_config())
        step = config.EMBED_BATCH_SIZE
        for i in range(0, len(chunks), step):
            store.add_documents(chunks[i:i + step], ids=ids[i:i + step])
            print(f"  embedded {min(i + step, len(chunks))}/{len(chunks)}")
        count = store._collection.count()
        if count != len(chunks):
            raise IndexProblem(f"Expected {len(chunks)} vectors but stored {count}.")

        info = {"embedding_model": config.EMBEDDING_MODEL, "distance": config.DISTANCE,
                "chunk_size": config.CHUNK_SIZE, "chunk_overlap": config.CHUNK_OVERLAP,
                "chunks": count, "built_at": datetime.now().isoformat(timespec="seconds")}
        (new_dir / INFO_FILE).write_text(json.dumps(info, indent=2), encoding="utf-8")

        # Only now does the new index become the active one (atomic swap).
        tmp = POINTER.with_suffix(".tmp")
        tmp.write_text(version, encoding="utf-8")
        os.replace(tmp, POINTER)
    except BaseException:
        shutil.rmtree(new_dir, ignore_errors=True)       # the previous index is untouched
        raise

    for old in config.INDEX_DIR.iterdir():               # remove superseded builds
        if old.is_dir() and old.name != version:
            shutil.rmtree(old, ignore_errors=True)
    return info, time.time() - start


# ---------------------------------------------------------------- open
def read_info():
    if not POINTER.exists():
        raise IndexProblem("No index found. Build one first: python index.py")
    version = POINTER.read_text(encoding="utf-8").strip()
    info_path = config.INDEX_DIR / version / INFO_FILE
    if not info_path.exists():
        raise IndexProblem("The index looks damaged. Rebuild it: python index.py")
    return version, json.loads(info_path.read_text(encoding="utf-8"))


def open_index():
    """Open the active index for searching. Refuses if the embedding model changed (Module 3.5)."""
    version, info = read_info()
    if info["embedding_model"] != config.EMBEDDING_MODEL:
        raise IndexProblem(
            f"The index was built with {info['embedding_model']} but the configured model is "
            f"{config.EMBEDDING_MODEL}. Vectors from different models can't be compared. "
            f"Rebuild the index: python index.py")
    store = Chroma(collection_name=config.COLLECTION_NAME,
                   embedding_function=get_embeddings(),
                   persist_directory=str(config.INDEX_DIR / version),
                   create_collection_if_not_exists=False)
    return store, info


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if "--info" in sys.argv:
            version, info = read_info()
            print(f"Active index {version}")
            for key, value in info.items():
                print(f"  {key}: {value}")
            return
        print(f"Building index with {config.EMBEDDING_MODEL} ({config.DISTANCE})")
        info, seconds = build_index()
        print(f"\nIndexed {info['chunks']} chunks in {seconds:.1f}s")
    except IndexProblem as problem:
        print(f"\nProblem: {problem}")
        sys.exit(1)


if __name__ == "__main__":
    main()