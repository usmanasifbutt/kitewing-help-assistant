"""verify.py - setup check (Capstone R7). Each failure says what to do next, in one or two plain sentences.

Run it first:  python verify.py
Imports of the heavy libraries happen inside the checks, so this script still works (and says
what is missing) when the packages are not installed yet.
"""
import importlib.util
import json
import os
import sys
import tempfile
import urllib.request

import config

MODULES = {  # import name -> pip name
    "langchain": "langchain", "langchain_chroma": "langchain-chroma",
    "langchain_huggingface": "langchain-huggingface",
    "langgraph": "langgraph", "chromadb": "chromadb",
    "sentence_transformers": "sentence-transformers", "rank_bm25": "rank-bm25",
    "pypdf": "pypdf", "docx2txt": "docx2txt",
}


def required_modules():
    """The packages needed for the active LLM provider are checked too."""
    extra = {"langchain_openai": "langchain-openai"} if config.LLM_PROVIDER == "openai" else {"langchain_ollama": "langchain-ollama"}
    return {**MODULES, **extra}


def check_python():
    ok = sys.version_info >= (3, 10)
    return ok, f"Python {sys.version.split()[0]}", "Install Python 3.12 and recreate the virtual environment."


def check_packages():
    missing = [pip for mod, pip in required_modules().items() if importlib.util.find_spec(mod) is None]
    return not missing, "Required packages installed", f"Run: pip install -r requirements.txt (missing: {', '.join(missing)})"


def check_ollama():
    try:
        with urllib.request.urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=3) as r:
            names = [m["name"] for m in json.load(r)["models"]]
    except Exception:
        return False, "Ollama is running", "Start Ollama (open the Ollama app, or run: ollama serve)."
    have = {n.split(":latest")[0] for n in names}
    missing = [m for m in dict.fromkeys((config.LLM_MODEL, config.JUDGE_MODEL)) if m not in have]
    if missing:
        return False, f"Model {', '.join(missing)} downloaded", f"Run: ollama pull {missing[0]}"
    return True, f"Ollama running, {config.LLM_MODEL} available", ""


def check_openai():
    if not os.environ.get("OPENAI_API_KEY"):
        return False, "OPENAI_API_KEY is set", "Add OPENAI_API_KEY to your .env file, or switch back with LLM_PROVIDER=ollama."
    return True, f"OpenAI selected, model {config.LLM_MODEL}, API key found", ""


def check_llm():
    """Checks whichever language-model provider is switched on (LLM_PROVIDER)."""
    return check_openai() if config.LLM_PROVIDER == "openai" else check_ollama()


def check_embeddings():
    import models
    size = len(models.get_embeddings().embed_query("test sentence"))
    return True, f"Embedding model {config.EMBEDDING_MODEL} works ({size} dimensions)", ""


def check_reranker():
    import models
    score = models.get_reranker().predict([("hello", "hello world")])[0]
    return True, f"Re-ranker {config.RERANKER_MODEL} works (test score {float(score):.1f})", ""


def check_chroma():
    import chromadb
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        collection = chromadb.PersistentClient(path=folder).create_collection("verify_test")
        collection.add(ids=["1"], documents=["hello"], embeddings=[[0.1, 0.2, 0.3]])
        count = collection.count()
    return count == 1, "Chroma can store and read vectors", "Reinstall it: pip install --force-reinstall chromadb"


def check_index():
    import index
    try:
        _, info = index.read_info()
    except index.IndexProblem as problem:
        return False, "Search index exists", str(problem)
    if info["embedding_model"] != config.EMBEDDING_MODEL:
        return False, "Index matches the embedding model", "The index was built with a different embedding model. Rebuild it: python index.py"
    return True, f"Index ready: {info['chunks']} chunks, built with {info['embedding_model']}", ""


CHECKS = (check_python, check_packages, check_llm, check_embeddings, check_reranker, check_chroma, check_index)
NEEDS_PACKAGES = {check_embeddings, check_reranker, check_chroma, check_index}


def main():
    print("Checking your setup. The first run downloads the embedding model and re-ranker (about 0.3 GB).\n")
    failed, packages_ok = 0, True
    for check in CHECKS:
        if check in NEEDS_PACKAGES and not packages_ok:
            print(f"[SKIP] {check.__name__.replace('check_', '')} (install the packages first)")
            continue
        try:
            ok, label, fix = check()
        except Exception as error:                  # a check must never crash the whole report
            first = (str(error).strip().splitlines() or [type(error).__name__])[0][:150]
            ok, label, fix = False, f"{check.__name__.replace('check_', '').replace('_', ' ')} check", \
                f"It failed with: {first}. If you are offline, connect once so the models can download."
        print(("[ OK ] " if ok else "[FAIL] ") + label)
        if not ok:
            print("       -> " + fix)
            failed += 1
            if check is check_packages:
                packages_ok = False
    print("\nAll checks passed." if not failed else f"\n{failed} check(s) failed. Fix them in order, then run verify.py again.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
