"""verify.py - setup check (Capstone R7). Each failure says what to do next."""
import importlib.util
import json
import sys
import urllib.request

import config

MODULES = {  # import name -> pip name
    "langchain": "langchain", "langchain_chroma": "langchain-chroma",
    "langchain_huggingface": "langchain-huggingface", "langchain_ollama": "langchain-ollama",
    "langgraph": "langgraph", "chromadb": "chromadb",
    "sentence_transformers": "sentence-transformers", "rank_bm25": "rank-bm25",
    "pypdf": "pypdf", "docx2txt": "docx2txt",
}


def check_python():
    ok = sys.version_info >= (3, 10)
    return ok, f"Python {sys.version.split()[0]}", "Install Python 3.12 and recreate the virtual environment."


def check_packages():
    missing = [pip for mod, pip in MODULES.items() if importlib.util.find_spec(mod) is None]
    return not missing, "Required packages installed", f"Run: pip install -r requirements.txt (missing: {', '.join(missing)})"


def check_ollama():
    try:
        with urllib.request.urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=3) as r:
            names = [m["name"] for m in json.load(r)["models"]]
    except Exception:
        return False, "Ollama is running", "Start Ollama (open the Ollama app, or run: ollama serve)."
    if config.LLM_MODEL not in names:
        return False, f"Model {config.LLM_MODEL} downloaded", f"Run: ollama pull {config.LLM_MODEL}"
    return True, f"Ollama running, {config.LLM_MODEL} available", ""


def main():
    failed = 0
    for check in (check_python, check_packages, check_ollama):
        ok, label, fix = check()
        print(("[ OK ] " if ok else "[FAIL] ") + label)
        if not ok:
            print("       -> " + fix)
            failed += 1
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()