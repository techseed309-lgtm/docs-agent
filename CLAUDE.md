# CLAUDE.md — working agreement and architecture

This file is for whoever (human or Claude Code) is working on this repo next. It's the
contract for *how* we build, not the sales pitch — that's [README.md](README.md), written
last.

## What this is

"docs-agent": point it at a folder of documents, it ingests and embeds them on a
schedule, and exposes a chat endpoint that answers questions from those documents with
citations. It refuses to answer when the documents don't cover the question.

The product is not the chatbot — the engineering around it is: a versioned workflow
repo, a repeatable ingestion pipeline, an eval harness with real numbers, cost logging,
and error handling that doesn't fail silently.

## Stack and hard constraints

- **n8n**, self-hosted via Docker Compose. Never n8n Cloud.
- **PostgreSQL 16 + pgvector**, one instance, two databases (`n8n`, `vectors`). No
  Pinecone/Qdrant/Weaviate/etc. — cutting that dependency is a deliberate cost decision
  and part of the pitch.
- Embeddings and chat model are **configurable via env vars** (`EMBEDDING_MODEL`,
  `CHAT_MODEL` in `.env`); never hardcode a model name inside a workflow node — read
  it from an env/credential expression instead. Default is **fully self-hosted via
  Ollama** (`nomic-embed-text` for embeddings, `llama3.2` for chat) — zero external
  API cost, zero API key, nothing in the corpus leaves the host. Changed from the
  original brief's OpenAI default; see "Environment notes" below for why and what
  it costs to switch back.
- **Python 3.11+** for scripts. Standard library first; any dependency needs a stated
  reason the stdlib doesn't cover.
- Demo UI is **one static HTML file** — no build step, no framework.
- Everything reproducible from a clean clone with `make up`.

## Repo layout

```
docs-agent/
├─ README.md              # case study, written LAST (M6)
├─ CLAUDE.md              # this file
├─ PLAN.md                # milestones with checkboxes, kept current
├─ .env.example           # every var, documented, no real values
├─ .gitignore
├─ Makefile                # up, down, logs, ps, reset, (+ import/export/ingest/eval from M1+)
├─ docker-compose.yml
├─ db/init/                # 01-databases.sql (M0), 02-schema.sql (M1)
├─ workflows/              # exported n8n workflow JSON — the source of truth
├─ scripts/
│  ├─ n8n_api.py           # export/import workflows via the n8n REST API
│  ├─ ingest_check.py      # verify chunk counts and embedding dims in Postgres
│  └─ eval.py              # run the golden set, write a scored report
├─ eval/
│  ├─ golden.yaml           # question / expected-source / expected-answer triples
│  └─ results/              # timestamped JSON + markdown reports
├─ corpus/sample/           # small public document set, committed
└─ ui/index.html            # chat demo that calls the n8n webhook
```

## Architecture (fills in as milestones land)

- **Postgres** is one instance serving two roles: n8n's own operational DB (`n8n`
  database) and the vector store (`vectors` database, `documents`/`chunks` tables with
  a pgvector HNSW index — see `db/init/02-schema.sql`, added in M1).
- **Ingestion workflow** (n8n, M1): reads `corpus/sample/`, chunks, embeds, upserts into
  `chunks`. Skips unchanged files via `content_sha` so re-ingestion is cheap.
- **Chat workflow** (`workflows/02-chat.json`, M2): webhook receives a question, embeds
  it, cosine-searches top-k chunks, assembles a cited prompt, calls the chat model,
  returns `{answer, sources[], usage}`. Refuses below a relevance floor
  (`RELEVANCE_THRESHOLD`) instead of guessing -- and skips calling the chat model
  entirely on that path. Note: Ollama unloads an idle model after a few minutes, so
  the first chat call after a lull pays a real one-time load cost (~60-70s for
  `llama3.2` on this machine) before generation even starts; the HTTP node's timeout
  is set generously (300s) to absorb that, not because generation itself is slow.
- **tenant column** exists in `documents`/`chunks` from day one (default `'default'`).
  Unused until M7, but it's the seam that turns this into a multi-tenant product later
  without a schema migration.
- **Eval harness** (`scripts/eval.py`, M3): scores retrieval hit rate, faithfulness (LLM
  judge), and refusal accuracy against `eval/golden.yaml`, writes to `eval/results/`.

## Working agreement

- Work **milestone by milestone**. Finish one, show what changed, wait for a go-ahead
  before starting the next. Don't run ahead.
- **One git commit per milestone**, conventional-commit style (`feat:`, `chore:`, etc.).
- **Secrets never enter git.** `.env` is gitignored; `.env.example` is committed with
  empty values and a one-line comment per var.
- **Before adding any dependency**, state what it is and why the standard library won't
  do.
- **Every script** takes `--help` and fails with a clear message when required env is
  missing — never a bare traceback.
- **When a workflow changes**, export it to `workflows/` so the JSON in git stays the
  truth (`scripts/n8n_api.py export`).
- **Eval harness before tuning.** M3 (baseline numbers) happens before M4 (tuning) — a
  number to improve on, not a vibe.
- **README.md is written at M6, not before.** It's a sales document; it needs the real
  eval numbers to be worth anything.

## Milestone status

See [PLAN.md](PLAN.md) for the full list and current checkbox state.

## Environment notes (this dev machine)

- Windows, no GNU `make` on PATH by default. Chocolatey install of `make` failed here
  (needs an elevated shell — lock-file permission error on `C:\ProgramData\chocolatey`).
  Worked around by copying `mingw32-make.exe` to `C:\Users\Rinatoh computer\bin\make.exe`
  and adding that folder to the **user** PATH (no admin needed). Open a new terminal for
  `make` to resolve; existing terminals need `mingw32-make` or a restart.
- The project's parent folder (`Businness 1`) has a space in its path. Considered
  renaming to `business-1` but decided against it: the hazard (GNU Make's list
  functions — `$(wildcard)`, `$(words)`, `$(word)`, prerequisite lists, `$(CURDIR)` —
  silently mis-split on a space, verified empirically) is fully avoidable by never
  using those Make constructs on absolute paths, which is a rule one author can hold
  to for a Makefile this small. Docker, git, and Python (pathlib/argv lists) all
  handle the space correctly already. If this repo ever grows multiple contributors
  or CI runners with less predictable path handling, revisit the rename — it's cheap
  to do later, just disruptive to do mid-session.
- Two host port collisions found and fixed while bringing M1's postgres back up:
  a native Windows Postgres service already on 5432, and an unrelated Docker
  project's Postgres already on 5433. Moved this project's postgres to host port
  `55432` (see docker-compose.yml). n8n's own connection to postgres is over the
  internal Docker network on 5432 regardless -- only host tools (scripts/*.py) use
  the remapped port.
- **Switched the default model provider from OpenAI to self-hosted Ollama**
  (explicit decision, not the brief's original default) to satisfy a hard "zero
  spend beyond the Claude subscription" constraint -- OpenRouter was considered
  first but only proxies *paid* embedding providers, it doesn't offer a free
  embedding model. Ollama runs as its own docker-compose service; `nomic-embed-text`
  (768-dim) handles embeddings, `llama3.2` handles chat, both pulled once into the
  `ollama_data` volume. Consequences worth remembering:
  - `db/init/02-schema.sql` uses `VECTOR(768)`, not the brief's `VECTOR(1536)` --
    768 is `nomic-embed-text`'s output width. Switching to a different embedding
    model later means changing this column's width (and re-ingesting everything),
    not just an env var.
  - Switching *back* to OpenAI means more than an env var too: it means using
    n8n's OpenAI nodes instead of the Ollama ones in every workflow, an OpenAI API
    key + n8n credential, and reverting the schema to `VECTOR(1536)`.
  - Local inference adds real RAM/CPU load to whatever machine runs it -- a
    consideration for the eventual VPS deploy target (see the original brief's
    notes on memory sizing), not just this dev machine.
