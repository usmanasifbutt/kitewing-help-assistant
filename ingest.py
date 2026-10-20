"""ingest.py - load, clean, deduplicate, chunk, tag (Capstone R1, Module 2).

Part A: load (Module 2.1) and clean (Module 2.5). Cleaning runs BEFORE chunking.
"""
import re
import sys
import csv
import hashlib
from collections import Counter, defaultdict
from functools import lru_cache
from itertools import combinations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader

import config
import models
import problems
from models import get_tokenizer

# ---------------------------------------------------------------- 2.1 loading
def load_file(path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return PyPDFLoader(str(path)).load()       # one Document per page
    if suffix == ".docx":
        return Docx2txtLoader(str(path)).load()    # one Document for the whole file
    return TextLoader(str(path), encoding="utf-8").load()


def load_all():
    if not config.DOCS_DIR.is_dir():
        raise problems.Problem(f"The documents folder was not found ({config.DOCS_DIR}). "
                               f"Put the Kitewing files in a folder named 'documents' next to the scripts.")
    docs = []
    for path in sorted(config.DOCS_DIR.iterdir()):
        if path.suffix.lower() not in (".pdf", ".docx", ".md"):
            continue
        try:
            loaded = load_file(path)
        except Exception as error:                  # one damaged file must not stop the others
            print(f"  warning: skipped {path.name}, it could not be read ({type(error).__name__})")
            continue
        for doc in loaded:
            doc.metadata["source_file"] = path.name
            if path.suffix.lower() == ".pdf":
                doc.metadata["page"] += 1          # loader counts from 0; people count from 1
            else:
                doc.metadata.pop("page", None)     # Word and Markdown have no pages
            docs.append(doc)
    if not docs:
        raise problems.Problem(f"No PDF, Word or Markdown files were found in {config.DOCS_DIR}.")
    return docs


# ---------------------------------------------------------------- 2.5 cleaning
# Each pattern must match the WHOLE line (^...$), so real sentences are never touched.
NOISE = [
    r"^Kitewing Software[^|]*\|.*\|.*$",                      # running header (two pipes)
    r"^(RESTRICTED\s*\|\s*)?Page \d+ of \d+\s*\|.*$",         # page footer
    r"^CONFIDENTIAL - FOR INTERNAL USE ONLY$",                # stamps
    r"^RESTRICTED - HR AND EXECUTIVE TEAM ONLY - DO NOT FORWARD$",
    r"^Was this page helpful\?\s*Yes\s*/\s*No$",
    r"^Skip to main content$",                                # wiki export furniture
    r"^The Perch\s*\|.*$",
    r"^Home >.*$",
    r"^Last edited by .*min read$",
    r"^On this page:.*$",
    r"^\[Back to top\]\(#top\)$",
    r"^.*Cookie settings.*$",
]
NOISE_RE = [re.compile(p) for p in NOISE]

# UTF-8 text that was decoded as cp1252 somewhere upstream
MOJIBAKE = {
    "â€™": "'", "â€˜": "'", "â€œ": '"', "â€\x9d": '"',
    "â€“": "-", "â€”": "-", "â€¦": "...", "Â ": " ",
}

HEADING = re.compile(r"^\d+(\.\d+)*\.?\s+\S.{0,70}$")         # "2.1 Employment status"
BULLET = re.compile(r"^\s*([-•*]|\d+\))\s+")


def fix_encoding(text):
    for bad, good in MOJIBAKE.items():
        text = text.replace(bad, good)
    return text


def remove_noise(text):
    kept = [ln for ln in text.splitlines() if not any(p.match(ln.strip()) for p in NOISE_RE)]
    return "\n".join(kept)


def _continues(prev, line):
    """True if `line` is the continuation of the sentence in `prev`."""
    if HEADING.match(prev) and not prev.endswith((".", ":")):
        return False                       # prev is a heading, so line starts a new paragraph
    if HEADING.match(line) or BULLET.match(line):
        return False                       # line starts a new heading or bullet
    return not prev.endswith((".", "!", "?", ":", ";"))


def repair_lines(text):
    """Join PDF lines that were broken mid-sentence."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            out.append("")
        elif out and out[-1] and _continues(out[-1], line):
            out[-1] += " " + line
        else:
            out.append(line)
    return "\n".join(out)


def clean_text(text, is_pdf):
    text = fix_encoding(text)
    text = remove_noise(text)
    if is_pdf:
        text = repair_lines(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ------------------------------------------------------- 2.4 catalog and tagging
def load_catalog():
    if not config.CATALOG_PATH.is_file():
        raise problems.Problem(f"catalog.csv was not found ({config.CATALOG_PATH}). "
                               f"It must sit next to the scripts: it holds each document's metadata.")
    with open(config.CATALOG_PATH, encoding="utf-8", newline="") as f:
        return {row["file"]: row for row in csv.DictReader(f)}


def clean_all(docs):
    for doc in docs:
        doc.page_content = clean_text(doc.page_content, is_pdf="page" in doc.metadata)
    return docs


def group_by_file(docs, catalog):
    """{file name: [its pages]}. Catalogued files first, so a copy never beats the original."""
    groups = defaultdict(list)
    for doc in docs:
        groups[doc.metadata["source_file"]].append(doc)
    return dict(sorted(groups.items(), key=lambda kv: (kv[0] not in catalog, kv[0])))


# ------------------------------------------------------------- duplicates
def full_text(pages):
    return "\n".join(p.page_content for p in pages)


def _normalize(text):
    return " ".join(text.lower().split())


def drop_exact_duplicates(groups):
    seen, kept, skipped = {}, {}, []
    for name, pages in groups.items():
        digest = hashlib.sha256(_normalize(full_text(pages)).encode("utf-8")).hexdigest()
        if digest in seen:
            skipped.append((name, seen[digest]))      # (duplicate, original)
        else:
            seen[digest] = name
            kept[name] = pages
    return kept, skipped


def shingles(text, n=5):
    words = _normalize(text).split()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def find_near_duplicates(groups, threshold):
    """Report-only: pairs of files whose 5-word shingles overlap heavily (Jaccard)."""
    sets = {name: shingles(full_text(pages)) for name, pages in groups.items()}
    pairs = []
    for a, b in combinations(sets, 2):
        union = sets[a] | sets[b]
        score = len(sets[a] & sets[b]) / len(union) if union else 0.0
        if score >= threshold:
            pairs.append((a, b, round(score, 2)))
    return pairs


# ------------------------------------------------------- 2.2 / 2.3 chunking


def count_tokens(text):
    return len(get_tokenizer().tokenize(text))


def make_splitter():
    return RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        get_tokenizer(), chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)


CATALOG_FIELDS = ("doc_id", "title", "doc_type", "department", "region",
                  "access_level", "status", "last_updated")


def chunk_and_tag(groups, catalog, splitter):
    chunks = []
    for name, pages in groups.items():
        row = catalog[name]
        for page_doc in pages:
            page = page_doc.metadata.get("page")
            for n, piece in enumerate(splitter.split_text(page_doc.page_content), start=1):
                meta = {k: row[k] for k in CATALOG_FIELDS}
                meta["source_file"] = name
                if page:
                    meta["page"] = page
                    meta["chunk_id"] = f"{row['doc_id']}-p{page:02d}-c{n:02d}"
                else:
                    meta["chunk_id"] = f"{row['doc_id']}-c{n:02d}"
                chunks.append(Document(page_content=piece, metadata=meta))
    return chunks


# ------------------------------------------------------------ the pipeline
def ingest():
    """Load, clean, dedupe, chunk, tag. Returns (chunks, report). index.py will call this."""
    catalog = load_catalog()
    docs = clean_all(load_all())
    groups = group_by_file(docs, catalog)
    groups, exact = drop_exact_duplicates(groups)
    uncatalogued = [n for n in groups if n not in catalog]
    groups = {n: p for n, p in groups.items() if n in catalog}
    near = find_near_duplicates(groups, config.NEAR_DUP_THRESHOLD)
    chunks = chunk_and_tag(groups, catalog, make_splitter())
    report = {"pages": len(docs), "files": len(groups), "exact": exact,
              "uncatalogued": uncatalogued, "near": near}
    return chunks, report


def write_preview(chunks):
    lines = []
    for c in chunks:
        m = c.metadata
        lines.append(f"##### {m['chunk_id']} | {count_tokens(c.page_content)} tokens | {m['title']} "
                     f"| region={m['region']} | {m['access_level']} | {m['status']}")
        lines.append(c.page_content)
        lines.append("")
    config.CHUNKS_PREVIEW_PATH.write_text("\n".join(lines), encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    
    overlap_pct = 100 * config.CHUNK_OVERLAP / config.CHUNK_SIZE
    print(f"Settings: chunk_size={config.CHUNK_SIZE} tokens, overlap={config.CHUNK_OVERLAP} "
          f"({overlap_pct:.0f}%), tokenizer={config.EMBEDDING_MODEL}")
    
    if not 300 <= config.CHUNK_SIZE <= 500 or not 10 <= overlap_pct <= 20:
        print("  note: the brief asks for 300-500 tokens and 10-20% overlap")
    
    if config.CHUNK_SIZE > 512:
        print("  WARNING: chunks above 512 tokens are silently truncated by bge-small")

    chunks, rep = ingest()
    print(f"\n1. Loaded and cleaned {rep['pages']} pages/documents")
    print(f"2. Exact duplicates skipped: {len(rep['exact'])}")
    for dup, orig in rep["exact"]:
        print(f"     {dup} is identical to {orig}")
    for name in rep["uncatalogued"]:
        print(f"   WARNING: {name} is not in catalog.csv, skipped")
    print(f"3. Near-duplicates (kept, not deleted): {len(rep['near'])}")
    for a, b, score in rep["near"]:
        print(f"     {a}  ~  {b}   similarity {score}")

    sizes = [count_tokens(c.page_content) for c in chunks]
    per_file = Counter(c.metadata["source_file"] for c in chunks)
    print(f"4. Chunks: {len(chunks)} from {rep['files']} files "
          f"(tokens min/avg/max: {min(sizes)}/{sum(sizes) // len(sizes)}/{max(sizes)})")
    for name, n in sorted(per_file.items()):
        print(f"     {name:42s} {n:3d}")
    
    write_preview(chunks)
    print(f"\nWrote {config.CHUNKS_PREVIEW_PATH.name}: read it!")


if __name__ == "__main__":
    problems.run(main)