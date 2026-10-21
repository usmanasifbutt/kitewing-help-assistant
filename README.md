# Kitewing Help Assistant

A command-line chatbot that answers Kitewing Software employees' questions (leave, expenses, IT error codes, and so on) **only from the company's own documents**. It shows which document and page every answer came from, says "I don't have that information" when the documents don't cover a question, and never shows restricted documents (such as salary bands) to the wrong person.

It runs **entirely on your own computer, for free**: no accounts, no API keys, no cloud services. (An optional OpenAI switch exists; it is off by default.)

Kitewing Software, its staff, documents and policies are fictional.

## How it works

```
documents  ->  ingest.py  ->  index.py  ->  retrieve.py  ->  generate.py  ->  chat.py
(PDF, Word,    clean, split   embed and     filter, search,  grounded,       the command-
 Markdown)     into chunks    store in      re-rank          cited answer    line chatbot
                              Chroma
```

1. **Ingest** loads every document, removes page headers and other noise, and cuts the text into small chunks tagged with the document's details (region, access level, status, date).
2. **Index** turns each chunk into a vector with a local embedding model and stores it in a local Chroma database.
3. **Retrieve** keeps only the chunks the asker is allowed to see, finds candidates by meaning and by keywords, and re-ranks them with a cross-encoder.
4. **Generate** sends the best chunks to a local language model with strict rules (answer only from the sources, cite them). If the best chunk is not relevant enough, the model is never called and a fallback message is shown.
5. **Chat** is the interactive command line. **Evaluate** measures how well all of this works.

## What you need

| | |
|---|---|
| Operating system | Windows 10/11, macOS 14+ (Apple silicon), or Linux |
| Memory | About 8 GB of RAM |
| Disk space | About 5 GB free |
| Python | 3.12 recommended (3.10 or newer works) |
| Internet | Needed once, to download the software and models |
| Graphics card | Not needed |

### Downloads

| What | Size | Notes |
|---|---|---|
| Ollama | 0.2 GB (macOS) / 1.5 GB (Windows, Linux) | Runs the language model |
| `llama3.2:3b` language model | 2.0 GB | Needs 3 to 4 GB of free RAM while answering |
| Python packages | about 0.25 GB download, about 1.3 GB installed | Mostly PyTorch |
| Embedding model and re-ranker | about 0.26 GB | Downloaded automatically the first time you use them |

## Setup

Do the steps in order. Each one has a check, and `python verify.py` at the end tells you if anything is missing.

### Windows (PowerShell)

1. Install **Python 3.12** from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
2. Install **Ollama** from https://ollama.com/download, then start it (it runs in the system tray).
3. Download the language model (one time, 2 GB):
   ```powershell
   ollama pull llama3.2:3b
   ```
4. Open PowerShell **in this project folder**, create a virtual environment and install the packages:
   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   If PowerShell refuses to run the activate script, run `Set-ExecutionPolicy -Scope Process Bypass` and try again.
5. Create your settings file:
   ```powershell
   Copy-Item .env.example .env
   ```

### macOS and Linux (Terminal)

1. Install **Python 3.12** from https://www.python.org/downloads/ (on macOS you can also use `brew install python@3.12`).
2. Install **Ollama** from https://ollama.com/download and start it (on Linux: `ollama serve` in a separate terminal if it is not already running).
3. Download the language model (one time, 2 GB):
   ```bash
   ollama pull llama3.2:3b
   ```
4. In a terminal **in this project folder**, create a virtual environment and install the packages:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```
   **Linux only:** install the CPU-only build of PyTorch first, otherwise pip downloads several gigabytes of GPU libraries you do not need:
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   ```
   Then, on every system:
   ```bash
   pip install -r requirements.txt
   ```
5. Create your settings file:
   ```bash
   cp .env.example .env
   ```

### Check the setup and build the index (all systems)

```
python verify.py     # checks everything and says how to fix anything that fails
python index.py      # reads the documents and builds the search index (a minute or two)
python verify.py     # run it again: now all seven checks pass
python chat.py       # start asking questions
```

The first time you run `verify.py`, six checks pass and the last one (the search index) fails with "No index found". That is expected: building the index is the next step. After `python index.py`, run `verify.py` again and you should see seven `[ OK ]` lines and "All checks passed."

The first run also downloads the embedding model and re-ranker (about 0.26 GB), so it needs an internet connection and can take a few minutes.

## Using the chatbot

```
python chat.py
```

Type a question in plain English. Under each answer you will see the source documents and pages. Then you are asked "Was this helpful? [y/n, or Enter to skip]"; your answer is saved to help improve the system.

| Command | What it does |
|---|---|
| `/region US`, `/region UK`, `/region none` | Whose policies apply. Documents that apply to everyone are always included |
| `/role employee`, `/role hr` | Who is asking. `hr` can also see restricted documents |
| `/archived on`, `/archived off` | Include older, archived versions of documents |
| `/debug on`, `/debug off` | Show the filter, the retrieved chunks, their scores, and why it answered or refused |
| `/status` | Show the current session settings |
| `/help` | List the commands |
| `/quit` | Leave (typing `quit` or `exit` also works) |

`/role` is a session setting, there is no login: it simulates who is asking so the access rules can be demonstrated.

Things to try:

```
/region UK
How many weeks of paid parental leave does a primary caregiver get?
What does error KSW-2210 mean?
What is the copay for a dental check-up?          (not in the documents: it says so)
Who won the 2022 FIFA World Cup?                  (not about Kitewing: it declines)
What is the salary band for a Director?           (refused as employee)
/role hr
What is the salary band for a Director?           (answered for HR)
Since we have unlimited vacation, how do I book three months off?   (it corrects the false assumption)
```

## The scripts

Every script can be run on its own. If something predictable goes wrong (Ollama not running, no index, a missing file) it prints one clear message, not a stack trace.

| Script | What it does | Example |
|---|---|---|
| `verify.py` | Checks Python, packages, Ollama and the model, the embedding model, the re-ranker, Chroma and the index | `python verify.py` |
| `ingest.py` | Loads, cleans, de-duplicates, splits and tags the documents. Prints a report and writes `chunks_preview.txt` so you can read the chunks | `python ingest.py` |
| `index.py` | Embeds the chunks and builds the search index. A failed rebuild never damages the working index. `--info` shows the active index | `python index.py` |
| `retrieve.py` | Shows the filter and the ranked chunks with scores for one question | `python retrieve.py "meal limit" --archived` |
| `generate.py` | Answers one question. `--calibrate` prints the re-ranker scores used to choose the confidence threshold | `python generate.py "KSW-2210" --role employee` |
| `chat.py` | The interactive chatbot (see above) | `python chat.py` |
| `evaluate.py` | Scores the system against `test_questions.json` | see below |

Options for `retrieve.py` and `generate.py`: `--role employee|hr`, `--region US|UK`, `--archived`. `retrieve.py` also has `--mode semantic|keyword|hybrid` and `--no-rerank`.

## Measuring quality

```
python evaluate.py --retrieval-only --label base   # fast: scores retrieval only, no language model
python evaluate.py --compare                       # semantic vs keyword vs hybrid vs hybrid + re-rank
python evaluate.py --label final                   # full run: answers are generated and graded by a second model call
python evaluate.py --questions Q05,Q09 --no-save   # just a few questions
```

- **Retrieval** is scored with precision@k, recall@k and MRR. A chunk counts as correct if it comes from the right document and contains the evidence text listed in the test set, so the scores stay valid when you change the chunk size.
- **Answers** are graded by a second model call (an "LLM judge") for correct behaviour (answered, declined, or corrected a false premise), faithfulness, relevance and completeness, each from 1 to 5. Judges are imperfect: read some answers yourself too.
- **Safety** is checked on every run: no restricted chunk may be shown to the employee role.
- Every run is saved in `eval_results/` with all the settings that produced it, and each new run prints which settings changed compared with the previous run.

A full run takes a few minutes per answered question on a laptop. Use `--retrieval-only` for quick checks.

### Running an experiment

Change exactly one setting, rebuild if needed, and run the same evaluation again:

1. Run `python evaluate.py --label baseline`.
2. Change one line in `.env`, for example `CHUNK_SIZE=200`.
3. If you changed `CHUNK_SIZE` or `CHUNK_OVERLAP`, rebuild: `python index.py`. (The evaluation refuses to run on an index that does not match the settings.)
4. Run `python evaluate.py --label chunk200` and read the comparison with the previous run.

The test set (`test_questions.json`) never needs editing.

## Settings

All settings live in `config.py`. Any of them can be overridden in your `.env` file (copy `.env.example`), so you never need to edit the code.

| Setting | Default | Meaning |
|---|---|---|
| `CHUNK_SIZE` | 400 | Chunk length in embedding-model tokens (300 to 500 recommended) |
| `CHUNK_OVERLAP` | 60 | Tokens shared between neighbouring chunks (10 to 20 percent) |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Local embedding model. Changing it needs `python index.py` |
| `RETRIEVAL_MODE` | `hybrid` | `semantic`, `keyword` or `hybrid` |
| `USE_RERANKER` | `true` | Re-rank the candidates with a cross-encoder |
| `CANDIDATES` | 20 | How many candidates the first search stage finds |
| `TOP_K` | 4 | How many chunks are sent to the language model |
| `CONFIDENCE_THRESHOLD` | -6.9 | Minimum re-ranker score needed to answer. Below it the chatbot refuses without calling the model. Chosen from the test set with `python generate.py --calibrate` |
| `LLM_MODEL`, `JUDGE_MODEL` | `llama3.2:3b` | The answering model and the grading model |
| `MAX_ANSWER_TOKENS` | 300 | Caps the length of each answer |

If you have 16 GB of RAM or more, you can try a larger model for better answers: `ollama pull llama3.1:8b`, then set `LLM_MODEL=llama3.1:8b` in `.env`.

### Optional: OpenAI instead of the local model

Off by default. To use it, put these in `.env` (never commit that file):

```
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key-here
```

This switches both the answering and the grading model. Everything else still runs locally. Set `LLM_PROVIDER=ollama` (or remove the line) to go back.

## Project files

```
documents/             the Kitewing knowledge base (PDF, Word, Markdown)
catalog.csv            details of each document: region, access level, status, date
test_questions.json    17 test questions with expected behaviour and evidence

config.py              every setting, in one place
verify.py              setup check
ingest.py              load, clean, de-duplicate, split, tag
index.py               embed and store in Chroma
retrieve.py            filter, hybrid search, re-rank
generate.py            grounded, cited answers and the confidence gate
chat.py                the interactive chatbot
evaluate.py            the evaluation suite

llm.py                 creates the language model (local Ollama or OpenAI)
models.py              loads the embedding model, re-ranker and tokenizer
problems.py            turns predictable failures into clear messages

eval_results/          saved evaluation runs
logs/                  chat logs and feedback (created when you chat; not committed)
chroma_index/          the search index (created by index.py; not committed)
```

## Troubleshooting

Start with `python verify.py`: it checks the common causes in order and says what to do.

| Problem | What to do |
|---|---|
| `python` is not found, or the wrong version is used | Install Python 3.12, then recreate the environment: delete `.venv` and repeat step 4 of the setup |
| Packages are missing, or `ModuleNotFoundError` | The virtual environment is not active. Re-run the activate command (`.venv\Scripts\Activate.ps1` on Windows, `source .venv/bin/activate` on macOS/Linux), then `pip install -r requirements.txt` |
| "Ollama is not running" | Start the Ollama app (Windows and macOS), or run `ollama serve` in another terminal (Linux). Then try again |
| "A model is not downloaded in Ollama" | Run `ollama pull llama3.2:3b` (or the name it shows) |
| "No index found" | Run `python index.py` |
| "The index was built with a different embedding model" or "chunk size" | Run `python index.py` to rebuild it with your current settings |
| A model "could not be downloaded or loaded" | The first run needs the internet to download about 0.26 GB. On a company network that inspects HTTPS traffic, downloads from huggingface.co can fail: try a different network, or download once at home. After the first download the project works offline |
| Starting is very slow and the screen fills with "Retrying" or "Could not reach the Hub" | You have no (or a poor) internet connection, and each model file is retried several times before the downloaded copy is used. Once the models have been downloaded, tell the libraries not to go online: PowerShell `$env:HF_HUB_OFFLINE="1"`, macOS/Linux `export HF_HUB_OFFLINE=1` |
| Answers are very slow | The model is too big for your computer. Use `llama3.2:3b`, and close other large programs. Use `evaluate.py --retrieval-only` for quick checks |
| Out of memory | Use `llama3.2:3b`, and make sure no other large model is loaded in Ollama (`ollama ps`, then `ollama stop <name>`) |
| Strange characters on Windows | Use Windows Terminal or PowerShell 7. The scripts already write UTF-8 |
| You want to start over | Delete the `chroma_index` and `logs` folders, then run `python index.py` |
| Something unexpected happens | Run the script again with `DEBUG=1` set to see the full error details (PowerShell: `$env:DEBUG="1"`; macOS/Linux: `DEBUG=1 python chat.py`) |
