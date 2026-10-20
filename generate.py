"""generate.py - grounded, cited, honest answers (Capstone R4, Module 5)."""
import argparse
import json
import re
import sys
from collections import defaultdict
from functools import lru_cache
from itertools import combinations
from typing import TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

import config
import index
import retrieve


class GenerationProblem(Exception):
    """A predictable generation problem. The message tells the user what to do next."""


# ------------------------------------------- 5.1 grounding rules (system message)
GROUNDING_RULES = """You are the Kitewing Help Assistant. You answer employees' questions about company policies and IT support.

Rules:
1. Answer ONLY from the numbered sources in the user's message. Never use outside knowledge, even if you know the answer.
2. Cite every claim with its source number, written exactly like [Source 2]. Cite only sources you were given.
3. You may paraphrase and combine sources. Never invent numbers, dates, names or document titles.
4. First check the question's assumptions. If the question takes something for granted that the sources contradict (example: "Since parking is free, where do I park?" when the sources say parking is paid), do not answer as if the assumption were true. Say politely that the assumption is not correct, state what the sources actually say, and answer the real question from that.
5. If the sources are unrelated to the question and do not contain the answer, say you do not have that information and suggest contacting the People Team (HR questions) or the IT Helpdesk (IT questions). It is fine to say you don't know. Do not offer related information as a substitute (for example, do not give a medical copay when asked about dental).
6. If sources disagree: use the CURRENT version of a policy and say so. If an older version differs, mention its value separately and label it as the old, archived version. If sources apply to different groups, such as US and UK staff, give each answer clearly labelled by group. Do not choose between groups.
7. Be concise: no more than 150 words."""


# ------------------------------------------- 5.2 labelled context (user message)
def source_label(n, doc):
    m = doc.metadata
    page = f", page {m['page']}" if "page" in m else ""
    old = ", ARCHIVED older version" if m["status"] == "archived" else ""
    return f"[Source {n}] {m['title']}{page}, region {m['region']}, last updated {m['last_updated']}{old}"


def _numbers(nums):
    return ", ".join(f"[Source {n}]" for n in nums)


def conflict_notes(docs):
    """5.5: tell the model about versions and regions in code instead of hoping it notices."""
    by_doc, meta = defaultdict(list), {}
    for n, doc in enumerate(docs, start=1):
        by_doc[doc.metadata["doc_id"]].append(n)
        meta[doc.metadata["doc_id"]] = doc.metadata
    notes = []
    for a, b in combinations(by_doc, 2):
        if a.rsplit("-", 1)[0] != b.rsplit("-", 1)[0]:        # HR-HB-US and HR-HB-UK share "HR-HB"
            continue
        ma, mb = meta[a], meta[b]
        if ma["status"] != mb["status"]:
            old, new = (a, b) if ma["status"] == "archived" else (b, a)
            notes.append(f"{_numbers(by_doc[new])} is the current version and {_numbers(by_doc[old])} "
                         f"is an older, archived version of the same policy. Use the current version, "
                         f"and you may mention that the older version differed.")
        elif ma["region"] != mb["region"]:
            notes.append(f"{_numbers(by_doc[a])} applies to {ma['region']} and {_numbers(by_doc[b])} "
                         f"applies to {mb['region']}. Give both answers, each labelled by region.")
    return notes


def build_messages(question, docs):
    blocks = [f"{source_label(n, d)}\n{d.page_content}" for n, d in enumerate(docs, start=1)]
    parts = ["Sources:\n\n" + "\n\n".join(blocks)]
    notes = conflict_notes(docs)
    if notes:
        parts.append("Notes about these sources:\n" + "\n".join(f"- {n}" for n in notes))
    parts.append(f"Question: {question}")
    return GROUNDING_RULES, "\n\n".join(parts)


# ------------------------------------------- 5.4 citation checks
STRAY_RE = re.compile(r"\[Source\s*(\d+)[^\]]*\]", re.I)
CITE_RE = re.compile(r"\[(?:Source\s*)?(\d+(?:\s*,\s*(?:Source\s*)?\d+)*)\]", re.I)


def normalize_citations(text):
    """Small models write [2], [Source 1, 2] or [Source 1, 4.3]. Make them all [Source N]."""
    text = CITE_RE.sub(lambda m: "".join(f"[Source {n}]" for n in re.findall(r"\d+", m.group(1))), text)
    return STRAY_RE.sub(lambda m: f"[Source {m.group(1)}]", text)


def verify_citations(text, n_sources):
    cited = [int(n) for n in re.findall(r"\[Source (\d+)\]", text)]
    bad = sorted({n for n in cited if not 1 <= n <= n_sources})
    for n in bad:
        text = text.replace(f"[Source {n}]", "")
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    warnings = [f"Removed [Source {n}]: the model cited a source it was never given." for n in bad]
    return text, warnings, sorted(set(cited) - set(bad))


# ------------------------------------------- the model
@lru_cache(maxsize=1)
def get_llm():
    return ChatOllama(model=config.LLM_MODEL, base_url=config.OLLAMA_URL,
                      temperature=0, num_predict=config.MAX_ANSWER_TOKENS)


def call_llm(system, user):
    try:
        return get_llm().invoke([("system", system), ("human", user)]).content
    except Exception as error:                  # predictable problems get a clear message
        text = str(error).lower()
        if "connect" in text or "refused" in text:
            raise GenerationProblem("Ollama is not running. Start the Ollama app (or run: ollama serve) and try again.")
        if "not found" in text:
            raise GenerationProblem(f"The model {config.LLM_MODEL} is not downloaded. Run: ollama pull {config.LLM_MODEL}")
        raise


# ------------------------------------------- 5.3 the graph: retrieve -> gate -> generate -> verify
class State(TypedDict, total=False):
    question: str
    asker: retrieve.Asker
    chunks: list
    answer: str
    refused: bool
    cited: list
    warnings: list


def retrieve_node(state):
    _, chunks = retrieve.retrieve(state["question"], state["asker"])
    return {"chunks": chunks}


def confident(chunks):
    """Confidence gate: is the best re-ranker score good enough to answer from?"""
    if not chunks:
        return False
    best = chunks[0][1]
    return True if best is None else best >= config.CONFIDENCE_THRESHOLD   # no score if the re-ranker is off


def gate(state):
    return "generate" if confident(state["chunks"]) else "fallback"


def fallback_node(state):
    return {"answer": config.FALLBACK_MESSAGE, "refused": True, "cited": [], "warnings": []}


def generate_node(state):
    system, user = build_messages(state["question"], [d for d, _ in state["chunks"]])
    return {"answer": call_llm(system, user)}


def verify_node(state):
    text, warnings, cited = verify_citations(normalize_citations(state["answer"]), len(state["chunks"]))
    if not cited:
        warnings.append("The answer cites no sources; check it against the documents.")
    return {"answer": text, "warnings": warnings, "cited": cited, "refused": False}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("generate", generate_node)
    graph.add_node("verify", verify_node)

    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges("retrieve", gate, ["generate", "fallback"])
    graph.add_edge("generate", "verify")
    graph.add_edge("verify", END)
    graph.add_edge("fallback", END)
    return graph.compile()


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()


def answer_question(question, asker):
    """The one function chat.py and evaluate.py will call."""
    state = get_graph().invoke({"question": question, "asker": asker})
    docs = [d for d, _ in state["chunks"]]
    sources = [{"n": n, "title": docs[n - 1].metadata["title"], "file": docs[n - 1].metadata["source_file"],
                "page": docs[n - 1].metadata.get("page")} for n in state["cited"]]
    return {"answer": state["answer"], "refused": state["refused"], "sources": sources,
            "warnings": state["warnings"], "chunks": state["chunks"]}


# ------------------------------------------- choose the threshold from data
def calibrate():
    questions = json.load(open(config.TEST_SET_PATH, encoding="utf-8"))["questions"]
    rows = []
    for q in questions:
        asker = retrieve.Asker(q["role"], q["region"], q["include_archived"])
        _, chunks = retrieve.retrieve(q["question"], asker, use_reranker=True)
        rows.append((chunks[0][1] if chunks else float("-inf"), q["id"], q["expected_behavior"], q["question"]))
    rows.sort()
    print("Best re-ranker score per question, lowest first:\n")
    for score, qid, behavior, text in rows:
        print(f"{score:8.2f}  {qid:4s} {behavior:15s} {text[:60]}")
    decline = [s for s, _, b, _ in rows if b == "decline"]
    answerable = [s for s, _, b, _ in rows if b != "decline"]
    if decline and answerable and max(decline) < min(answerable):
        print(f"\nHighest decline score: {max(decline):.2f}   Lowest answerable score: {min(answerable):.2f}")
        print(f"Clean gap. A threshold in between works, for example {(max(decline) + min(answerable)) / 2:.1f}")
    else:
        print("\nThe scores overlap: no single threshold separates them. Look at the rows around the overlap.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Ask one question and see the grounded answer.")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--role", default="employee", choices=config.ROLES)
    parser.add_argument("--region", choices=config.REGIONS)
    parser.add_argument("--archived", action="store_true")
    parser.add_argument("--calibrate", action="store_true", help="print re-ranker scores for the test set")
    args = parser.parse_args()
    try:
        if args.calibrate:
            calibrate()
            return
        if not args.question:
            parser.error("give a question, or use --calibrate")
        result = answer_question(args.question, retrieve.Asker(args.role, args.region, args.archived))
    except (ValueError, index.IndexProblem, GenerationProblem) as problem:
        print(f"Problem: {problem}")
        sys.exit(1)
    print(result["answer"])
    for warning in result["warnings"]:
        print(f"\n! {warning}")
    if result["sources"]:
        print("\nSources:")
        for s in result["sources"]:
            page = f", page {s['page']}" if s["page"] else ""
            print(f"  [Source {s['n']}] {s['title']}{page} ({s['file']})")


if __name__ == "__main__":
    main()