"""evaluate.py - measure retrieval and answer quality (Capstone R6, Modules 4.4, 5.4, 6.2, 6.4)."""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime

import config
import problems
import generate
import index
import llm
import retrieve

PROMPT_VERSION = hashlib.sha1(generate.GROUNDING_RULES.encode("utf-8")).hexdigest()[:8]
BEHAVIOR_FOR = {"answer": "answered", "decline": "declined", "correct_premise": "corrected_premise"}
SCORES = ("faithfulness", "relevance", "completeness")
COMPARE_CONFIGS = [("semantic", "semantic", False), ("keyword", "keyword", False),
                   ("hybrid", "hybrid", False), ("hybrid + re-rank", "hybrid", True)]

JUDGE_INSTRUCTIONS = """You are a strict grader of an internal company help chatbot.
You are given a question, the sources the chatbot was shown, what a complete answer must contain, and the chatbot's answer.
Judge ONLY the answer text. Return a JSON object with exactly these keys:
  "behavior": "answered", "declined" or "corrected_premise"
      answered = it gave an answer from the sources
      declined = it said it does not have the information or cannot help
      corrected_premise = it pointed out that the question assumes something untrue and gave the real information
  "faithfulness": 1-5. 5 = every claim is supported by the sources; 1 = it invents things not in the sources.
  "relevance": 1-5. 5 = it directly addresses the question asked; 1 = it is off topic.
  "completeness": 1-5. 5 = it contains everything in the reference answer; 1 = it misses most of it.
  "explanation": one or two sentences explaining the scores."""


# ------------------------------------------- 4.4 retrieval metrics, matched on evidence text
def norm(text):
    return " ".join(text.lower().split())


def holds(doc, evidence):
    """A chunk holds an evidence passage if it is from that file and contains that exact text.
    Matching on text, not chunk IDs, keeps the test set valid when the chunk size changes."""
    return doc.metadata["source_file"] == evidence["source"] and norm(evidence["contains"]) in norm(doc.page_content)


def retrieval_metrics(docs, evidence, k):
    if not evidence:
        return None                                   # decline questions have no correct chunks
    top = docs[:k]
    flags = [any(holds(d, e) for e in evidence) for d in top]
    return {
        "precision": sum(flags) / len(top) if top else 0.0,                      # relevant chunks / k
        "recall": sum(any(holds(d, e) for d in top) for e in evidence) / len(evidence),   # passages found
        "mrr": next((1 / rank for rank, hit in enumerate(flags, start=1) if hit), 0.0),   # 1 / first hit
    }


# ------------------------------------------- 6.2 LLM as judge
def judge_answer(q, answer, docs):
    sources = "\n\n".join(f"{generate.source_label(n, d)}\n{d.page_content[:700]}" for n, d in enumerate(docs, start=1))
    user = (f"Question: {q['question']}\n\nWhat a complete answer must contain (reference answer): "
            f"{q['reference_answer']}\n\nSources the chatbot was shown:\n{sources}\n\nChatbot answer:\n{answer}")
    judge = llm.get_chat_model(config.JUDGE_MODEL, 400, json_mode=True)
    for _ in range(2):                                # one retry if the JSON is unusable
        reply = llm.ask(judge, [("system", JUDGE_INSTRUCTIONS), ("human", user)])   # provider errors raise GenerationProblem
        try:
            data = json.loads(reply)
            judged = {s: max(1, min(5, int(data[s]))) for s in SCORES}
            judged["behavior"] = str(data["behavior"]).strip().lower()
            judged["explanation"] = str(data.get("explanation", "")).strip()
            return judged
        except (ValueError, KeyError, TypeError):
            continue
    return None


# ------------------------------------------- running one question
def run_question(q, retrieval_only):
    asker = retrieve.Asker(q["role"], q["region"], q["include_archived"])
    start = time.time()
    row = {"id": q["id"], "category": q["category"], "question": q["question"],
           "expected": BEHAVIOR_FOR[q["expected_behavior"]],
           "answer": None, "refused": None, "behavior": None, "judge": None, "warnings": [], "error": None}
    try:
        if retrieval_only:
            _, ranked = retrieve.retrieve(q["question"], asker)
        else:
            result = generate.answer_question(q["question"], asker)
            ranked = result["chunks"]
            row.update(answer=result["answer"], refused=result["refused"], warnings=result["warnings"])
            if result["refused"]:
                row["behavior"] = "declined"            # the gate refused: there is no model answer to judge
            else:
                row["judge"] = judge_answer(q, result["answer"], [d for d, _ in ranked])
                row["behavior"] = row["judge"]["behavior"] if row["judge"] else None
    except (index.IndexProblem, generate.GenerationProblem):
        raise                                           # global problems stop the run with a clear message
    except Exception as error:                          # one odd question must not end the whole run
        row["error"] = f"{type(error).__name__}: {error}"
        ranked = []
    docs = [d for d, _ in ranked]
    row["chunks"] = [{"chunk_id": d.metadata["chunk_id"], "score": None if s is None else round(s, 3)} for d, s in ranked]
    row["retrieval"] = retrieval_metrics(docs, q["evidence"], config.TOP_K)
    # safety check: no restricted chunk may ever reach anyone but HR
    row["leaked"] = [d.metadata["chunk_id"] for d in docs if d.metadata["access_level"] == "restricted" and q["role"] != "hr"]
    row["seconds"] = round(time.time() - start, 1)
    row["problems"] = find_problems(row, retrieval_only)
    return row


def find_problems(row, retrieval_only):
    if row["error"]:
        return [f"error: {row['error']}"]
    problems = []
    if row["leaked"]:
        problems.append(f"RESTRICTED CHUNK SHOWN TO EMPLOYEE: {', '.join(row['leaked'])}")
    if retrieval_only:
        if row["retrieval"] and row["retrieval"]["recall"] < 1.0:
            problems.append(f"recall {row['retrieval']['recall']:.2f}: not every evidence passage was retrieved")
        return problems
    if row["behavior"] != row["expected"]:
        problems.append(f"behavior: expected {row['expected']}, got {row['behavior']}")
    if row["judge"] and row["expected"] != "declined":
        for name in SCORES:
            if row["judge"][name] <= 2:
                problems.append(f"low {name} ({row['judge'][name]})")
    return problems


# ------------------------------------------- summary and printing
def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def summarize(rows):
    retr = [r["retrieval"] for r in rows if r["retrieval"]]
    judged = [r["judge"] for r in rows if r["judge"] and r["expected"] != "declined"]
    return {
        "questions": len(rows),
        "passed": sum(1 for r in rows if not r["problems"]),
        "precision": mean([x["precision"] for x in retr]),
        "recall": mean([x["recall"] for x in retr]),
        "mrr": mean([x["mrr"] for x in retr]),
        "faithfulness": mean([j["faithfulness"] for j in judged]),
        "relevance": mean([j["relevance"] for j in judged]),
        "completeness": mean([j["completeness"] for j in judged]),
        "leaks": sum(len(r["leaked"]) for r in rows),
    }


def fmt(value, digits=2):
    return "  - " if value is None else f"{value:.{digits}f}"


def print_table(rows):
    print(f"\n{'ID':4s} {'expected':17s} {'got':17s} {'P@k':>5s} {'R@k':>5s} {'MRR':>5s} {'faith':>5s} {'rel':>5s} {'compl':>5s}  result")
    for r in rows:
        m, j = r["retrieval"], r["judge"]
        print(f"{r['id']:4s} {r['expected']:17s} {str(r['behavior'] or '-'):17s} "
              f"{fmt(m and m['precision']):>5s} {fmt(m and m['recall']):>5s} {fmt(m and m['mrr']):>5s} "
              f"{(str(j['faithfulness']) if j else '-'):>5s} {(str(j['relevance']) if j else '-'):>5s} "
              f"{(str(j['completeness']) if j else '-'):>5s}  {'ok' if not r['problems'] else 'FAIL'}")


def print_summary(s, retrieval_only):
    print(f"\nPassed {s['passed']}/{s['questions']}")
    print(f"Retrieval  precision@{config.TOP_K} {fmt(s['precision'])}   recall@{config.TOP_K} {fmt(s['recall'])}   MRR {fmt(s['mrr'])}")
    if not retrieval_only:
        print(f"Answers    faithfulness {fmt(s['faithfulness'])}   relevance {fmt(s['relevance'])}   "
              f"completeness {fmt(s['completeness'])}   (scale 1-5)")
    print(f"Safety     restricted chunks shown to employees: {s['leaks']}")


def print_failures(rows):
    failed = [r for r in rows if r["problems"]]
    if not failed:
        print("\nNo failures.")
        return
    print(f"\n{len(failed)} failure(s):")
    for r in failed:
        print(f"\n--- {r['id']} ({r['category']}): {r['question']}")
        for problem in r["problems"]:
            print(f"    problem: {problem}")
        if r["answer"]:
            print(f"    answer: {r['answer'][:400]}")
        if r["judge"]:
            print(f"    judge: {r['judge']['explanation']}")


# ------------------------------------------- 6.4 saved runs and comparison
def run_settings():
    settings = config.current_settings()
    settings["PROMPT_VERSION"] = PROMPT_VERSION
    return settings


def save_run(label, rows, summary, retrieval_only):
    config.EVAL_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = config.EVAL_DIR / f"run_{stamp}{'_' + label if label else ''}.json"
    record = {"label": label, "time": datetime.now().isoformat(timespec="seconds"),
              "retrieval_only": retrieval_only, "settings": run_settings(), "summary": summary, "results": rows}
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def previous_run(current_path):
    runs = sorted(p for p in config.EVAL_DIR.glob("run_*.json") if p != current_path)
    return (runs[-1], json.loads(runs[-1].read_text(encoding="utf-8"))) if runs else (None, None)


def print_comparison(old_path, old, settings, summary):
    print(f"\nCompared with the previous run ({old_path.name}):")
    if old["summary"]["questions"] != summary["questions"]:
        print(f"  note: the previous run covered {old['summary']['questions']} questions, this one {summary['questions']}")
    changed = {k: (old["settings"].get(k), v) for k, v in settings.items() if old["settings"].get(k) != v}
    if changed:
        print("  settings changed:")
        for key, (before, after) in changed.items():
            print(f"    {key}: {before} -> {after}")
    else:
        print("  settings changed: none")
    for name in ("precision", "recall", "mrr", "faithfulness", "relevance", "completeness"):
        before, after = old["summary"].get(name), summary.get(name)
        if before is not None and after is not None:
            print(f"  {name:13s} {before:.2f} -> {after:.2f}  ({after - before:+.2f})")


# ------------------------------------------- comparison mode
def compare_mode(questions):
    print(f"Retrieval comparison over {len(questions)} questions (top {config.TOP_K} chunks)\n")
    print(f"{'configuration':18s} {'precision':>9s} {'recall':>7s} {'MRR':>6s}")
    for name, mode, rerank in COMPARE_CONFIGS:
        metrics = []
        for q in questions:
            asker = retrieve.Asker(q["role"], q["region"], q["include_archived"])
            _, ranked = retrieve.retrieve(q["question"], asker, mode=mode, use_reranker=rerank)
            m = retrieval_metrics([d for d, _ in ranked], q["evidence"], config.TOP_K)
            if m:
                metrics.append(m)
        print(f"{name:18s} {fmt(mean([m['precision'] for m in metrics])):>9s} "
              f"{fmt(mean([m['recall'] for m in metrics])):>7s} {fmt(mean([m['mrr'] for m in metrics])):>6s}")


def check_index_matches_settings():
    """A11: if you change the chunk size you must rebuild the index before evaluating."""
    _, info = index.read_info()
    if info["chunk_size"] != config.CHUNK_SIZE or info["chunk_overlap"] != config.CHUNK_OVERLAP:
        raise index.IndexProblem(
            f"The index was built with chunk size {info['chunk_size']} / overlap {info['chunk_overlap']} but the "
            f"settings say {config.CHUNK_SIZE} / {config.CHUNK_OVERLAP}. Rebuild it first: python index.py")


def load_questions(only):
    data = json.loads(config.TEST_SET_PATH.read_text(encoding="utf-8"))["questions"]
    if not only:
        return data
    wanted = [i.strip().upper() for i in only.split(",")]
    unknown = [i for i in wanted if i not in {q["id"] for q in data}]
    if unknown:
        raise ValueError(f"Unknown question id(s): {', '.join(unknown)}")
    return [q for q in data if q["id"] in wanted]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Score retrieval and answer quality against the test set.")
    parser.add_argument("--retrieval-only", action="store_true", help="skip the model: score retrieval only (fast)")
    parser.add_argument("--compare", action="store_true", help="semantic vs keyword vs hybrid vs hybrid + re-rank")
    parser.add_argument("--label", default="", help="a short name added to the saved run file")
    parser.add_argument("--questions", help="only these ids, e.g. Q05,Q09")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    try:
        questions = load_questions(args.questions)
        check_index_matches_settings()
        if args.compare:
            compare_mode(questions)
            return
        rows = []
        for q in questions:
            print(f"  running {q['id']}...", flush=True)
            rows.append(run_question(q, args.retrieval_only))
    except (ValueError, index.IndexProblem, generate.GenerationProblem) as problem:
        print(f"Problem: {problem}")
        sys.exit(1)

    summary = summarize(rows)
    print_table(rows)
    print_summary(summary, args.retrieval_only)
    print_failures(rows)
    if args.no_save:
        return
    path = save_run(args.label, rows, summary, args.retrieval_only)
    print(f"\nSaved {path.relative_to(config.ROOT)}")
    old_path, old = previous_run(path)
    if old:
        print_comparison(old_path, old, run_settings(), summary)
    else:
        print("No previous run to compare with.")


if __name__ == "__main__":
    problems.run(main)