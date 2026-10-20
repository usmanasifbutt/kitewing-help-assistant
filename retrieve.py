"""retrieve.py - filter, hybrid search and re-ranking (Capstone R3, Module 4)."""
import argparse
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

import config
import models
import problems
from models import get_reranker
import index


@dataclass
class Asker:
    role: str = "employee"              # employee | hr
    region: Optional[str] = None        # US | UK | None (no preference)
    include_archived: bool = False


# ----------------------------------------------- 4.2 / 6.1 pre-filtering
def build_filter(asker):
    """Who is asking -> Chroma metadata filter. Applied BEFORE any search."""
    if asker.role not in config.ROLES:
        raise ValueError(f"Unknown role '{asker.role}'. Choose from: {', '.join(config.ROLES)}")
    
    if asker.region and asker.region not in config.REGIONS:
        raise ValueError(f"Unknown region '{asker.region}'. Choose from: {', '.join(config.REGIONS)}")
    
    levels = ["internal"] + (["restricted"] if asker.role == "hr" else [])
    
    clauses = [{"access_level": {"$in": levels}}]
    if asker.region:
        clauses.append({"region": {"$in": [asker.region, "Global"]}})   # Global is always included
    if not asker.include_archived:
        clauses.append({"status": {"$eq": "current"}})
    
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


@lru_cache(maxsize=1)
def get_store():
    store, _ = index.open_index()       # also checks the embedding model matches
    return store


def eligible_chunks(store, where):
    data = store.get(where=where, include=["documents", "metadatas"])
    return [Document(page_content=t, metadata=m) for t, m in zip(data["documents"], data["metadatas"])]


# ------------------------------------------------------ 4.1 keyword search
TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")      # keeps KSW-2210 and HR-118 whole


def tokenize(text):
    out = []
    for token in TOKEN_RE.findall(text.lower()):
        out.append(token)
        if "-" in token:
            out.extend(token.split("-"))                # "work-from-abroad" also matches its parts
    return out


def keyword_search(chunks, query, n):
    if not chunks:
        return []
    bm25 = BM25Okapi([tokenize(c.page_content) for c in chunks])   # built over eligible chunks only
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(zip(chunks, scores), key=lambda pair: -pair[1])
    return [c for c, score in ranked[:n] if score > 0]


def semantic_search(store, query, where, n):
    return [d for d, _ in store.similarity_search_with_score(query, k=n, filter=where)]


# ------------------------------------------------------------- 4.1 fusion
def rrf(lists, k=60):
    """Reciprocal Rank Fusion: a chunk scores 1/(k+rank) in every list it appears in."""
    scores, by_id = {}, {}
    for ranked in lists:
        for pos, doc in enumerate(ranked, start=1):
            cid = doc.metadata["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + pos)
            by_id[cid] = doc
    return [by_id[c] for c in sorted(scores, key=scores.get, reverse=True)]


# --------------------------------------------------------- 4.3 re-ranking


def rerank(query, docs, top_k):
    if not docs:
        return []
    scores = get_reranker().predict([(query, d.page_content) for d in docs])   # raw logits, not 0-1
    ranked = sorted(zip(docs, scores), key=lambda pair: -pair[1])[:top_k]
    return [(d, float(s)) for d, s in ranked]


# --------------------------------------------------------------- the pipeline
def retrieve(query, asker, mode=None, use_reranker=None, top_k=None):
    """Returns (filter used, [(chunk, rerank score or None)]), best first."""
    mode = mode or config.RETRIEVAL_MODE
    use_reranker = config.USE_RERANKER if use_reranker is None else use_reranker
    top_k = top_k or config.TOP_K

    store = get_store()
    where = build_filter(asker)
    lists = []
    if mode in ("semantic", "hybrid"):
        lists.append(semantic_search(store, query, where, config.CANDIDATES))
    if mode in ("keyword", "hybrid"):
        lists.append(keyword_search(eligible_chunks(store, where), query, config.CANDIDATES))
    candidates = rrf(lists)[:config.CANDIDATES]          # stage one: a wide net (~20)
    if use_reranker:
        return where, rerank(query, candidates, top_k)   # stage two: pick the best few
    return where, [(d, None) for d in candidates[:top_k]]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Show the filter and ranked chunks for a question.")
    parser.add_argument("question")
    parser.add_argument("--role", default="employee", choices=config.ROLES)
    parser.add_argument("--region", choices=config.REGIONS)
    parser.add_argument("--archived", action="store_true", help="include archived documents")
    parser.add_argument("--mode", default=config.RETRIEVAL_MODE, choices=("semantic", "keyword", "hybrid"))
    parser.add_argument("--no-rerank", action="store_true")
    args = parser.parse_args()
    try:
        asker = Asker(args.role, args.region, args.archived)
        where, ranked = retrieve(args.question, asker, args.mode, False if args.no_rerank else None)
    except (ValueError, index.IndexProblem) as problem:
        print(f"Problem: {problem}")
        sys.exit(1)
    print(f"Filter: {where}\nMode: {args.mode}, rerank: {not args.no_rerank and config.USE_RERANKER}\n")
    for rank, (doc, score) in enumerate(ranked, start=1):
        shown = "n/a" if score is None else f"{score:.2f}"
        m = doc.metadata
        print(f"{rank}. [{shown}] {m['chunk_id']}  {m['title']} (region {m['region']}, {m['status']})")
        print(f"   {doc.page_content[:160]!r}\n")


if __name__ == "__main__":
    problems.run(main)