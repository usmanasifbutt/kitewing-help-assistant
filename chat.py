"""chat.py - the command-line help assistant (Capstone R5, Modules 1 and 6)."""
import hashlib
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime

import config
import problems
import generate
import index
import retrieve
import verify

# A short fingerprint of the grounding prompt, logged with every answer (Module 6.5)
PROMPT_VERSION = hashlib.sha1(generate.GROUNDING_RULES.encode("utf-8")).hexdigest()[:8]

HELP = """Ask a question in plain English, or use a command:
  /region US|UK|none   set whose policies apply (Global documents always apply)
  /role employee|hr    set who is asking (hr can also see restricted documents)
  /archived on|off     include older, archived document versions
  /debug on|off        show the filter, retrieved chunks and scores
  /status              show the current session settings
  /help                show this help
  /quit                leave (you can also type quit or exit)"""


@dataclass
class Session:
    asker: retrieve.Asker = field(default_factory=retrieve.Asker)
    debug: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


# ------------------------------------------------- 6.3 / 6.5 logging
def write_log(filename, record):
    """Append one JSON line. A logging problem must never stop the chat."""
    try:
        config.LOG_DIR.mkdir(exist_ok=True)
        with open(config.LOG_DIR / filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as problem:
        print(f"(could not write {filename}: {problem})")


def log_interaction(session, question, seconds, result=None, error=None):
    record = {
        "id": uuid.uuid4().hex[:8],
        "session": session.id,
        "time": datetime.now().isoformat(timespec="seconds"),
        "asker": asdict(session.asker),
        "question": question,
        "seconds": round(seconds, 1),
        "prompt_version": PROMPT_VERSION,
        "settings": config.current_settings(),       # everything needed to replay this answer
    }
    if result:
        record.update({
            "answer": result["answer"],
            "refused": result["refused"],
            "warnings": result["warnings"],
            "cited": [{"n": s["n"], "file": s["file"], "page": s["page"]} for s in result["sources"]],
            "chunks": [{"chunk_id": d.metadata["chunk_id"], "score": None if s is None else round(s, 3)}
                       for d, s in result["chunks"]],
        })
    if error:
        record["error"] = error
    write_log("interactions.jsonl", record)
    return record["id"]


def ask_feedback(session, interaction_id):
    try:
        reply = input("Was this helpful? [y/n, or Enter to skip] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if reply in ("y", "n"):
        write_log("feedback.jsonl", {"interaction": interaction_id, "session": session.id,
                                     "time": datetime.now().isoformat(timespec="seconds"),
                                     "helpful": reply == "y"})
        print("Thanks, noted." if reply == "y" else "Thanks, noted. This will be reviewed.")


# ------------------------------------------------- showing answers
def show_result(result):
    print("\n" + result["answer"])
    for warning in result["warnings"]:
        print(f"\n! {warning}")
    seen, lines = set(), []
    for s in result["sources"]:
        key = (s["file"], s["page"])
        if key not in seen:
            seen.add(key)
            page = f", page {s['page']}" if s["page"] else ""
            lines.append(f"  {s['title']}{page} ({s['file']})")
    if lines:
        print("\nSources:\n" + "\n".join(lines))


def show_debug(session, result):
    print(f"\n[debug] filter: {retrieve.build_filter(session.asker)}")
    print(f"[debug] confidence threshold: {config.CONFIDENCE_THRESHOLD}")
    for rank, (doc, score) in enumerate(result["chunks"], start=1):
        shown = "n/a" if score is None else f"{score:.2f}"
        m = doc.metadata
        print(f"[debug] {rank}. score {shown}  {m['chunk_id']}  {m['title']}")
        print(f"[debug]    {' '.join(doc.page_content.split())[:110]}")
    print(f"[debug] decision: {'refused (below threshold)' if result['refused'] else 'answered'}")


# ------------------------------------------------- commands
def show_status(session):
    a = session.asker
    print(f"role={a.role}, region={a.region or 'any'}, archived={'on' if a.include_archived else 'off'}, "
          f"debug={'on' if session.debug else 'off'}, model={config.LLM_PROVIDER}:{config.LLM_MODEL}")


def parse_switch(args):
    if args and args[0] in ("on", "off"):
        return args[0] == "on"
    print("Use: on or off")
    return None


def handle_command(session, line):
    """Returns True when the user wants to leave."""
    parts = line.lstrip("/").split()
    if not parts:
        return False
    command, args = parts[0].lower(), [p.lower() for p in parts[1:]]
    if command in ("quit", "exit", "q"):
        return True
    if command == "help":
        print(HELP)
    elif command == "status":
        show_status(session)
    elif command == "region":
        value = args[0].upper() if args else ""
        if value == "NONE":
            session.asker.region = None
        elif value in config.REGIONS:
            session.asker.region = value
        else:
            print(f"Choose a region: {', '.join(config.REGIONS)} or none")
            return False
        show_status(session)
    elif command == "role":
        if args and args[0] in config.ROLES:
            session.asker.role = args[0]
            show_status(session)
        else:
            print(f"Choose a role: {', '.join(config.ROLES)}")
    elif command == "archived":
        value = parse_switch(args)
        if value is not None:
            session.asker.include_archived = value
            show_status(session)
    elif command == "debug":
        value = parse_switch(args)
        if value is not None:
            session.debug = value
            show_status(session)
    else:
        print(f"Unknown command '/{command}'. Type /help to see the commands.")
    return False


# ------------------------------------------------- one question
def handle_question(session, question):
    start = time.time()
    try:
        result = generate.answer_question(question, session.asker)
    except (ValueError, index.IndexProblem, generate.GenerationProblem) as problem:
        print(f"\nProblem: {problem}")
        log_interaction(session, question, time.time() - start, error=str(problem))
        return
    except Exception as error:                      # never stop the chat (R5)
        print(f"\nSomething went wrong answering that question ({type(error).__name__}). "
              f"You can keep chatting; try rephrasing it.")
        log_interaction(session, question, time.time() - start, error=f"{type(error).__name__}: {error}")
        return
    show_result(result)
    if session.debug:
        show_debug(session, result)
    interaction_id = log_interaction(session, question, time.time() - start, result=result)
    print()
    ask_feedback(session, interaction_id)


def start_up():
    """Check Ollama and warm up the models, so the first question is not slow."""
    ok, _, fix = verify.check_llm()
    if not ok:
        print(f"Warning: answers will fail until this is fixed. {fix}\n")
    print("Loading models (a few seconds)...")
    try:
        retrieve.get_store()
        retrieve.get_reranker()
    except index.IndexProblem as problem:
        print(f"\nProblem: {problem}")
        return False
    return True


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("Kitewing Help Assistant. Type /help for commands, /quit to leave.\n")
    if not start_up():
        sys.exit(1)
    session = Session()
    show_status(session)
    while True:
        a = session.asker
        prompt = f"\n[{a.role} | {a.region or 'any region'}{' | archived' if a.include_archived else ''}] > "
        try:
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith("/") or line.lower() in ("quit", "exit", "help"):
            if handle_command(session, line):
                break
            continue
        handle_question(session, line)
    print("Goodbye.")


if __name__ == "__main__":
    problems.run(main)