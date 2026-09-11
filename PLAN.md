# PLAN.md

Milestones, kept current. Work happens one milestone at a time — finish, show, wait for
a go-ahead, then move on (see [CLAUDE.md](CLAUDE.md)).

## M0 — Scaffold and stack

Repo tree, Docker Compose, Postgres+pgvector, n8n up and healthy, Makefile, git init.

**Done when:** `make reset && make up` from a clean clone gives a working n8n at
localhost:5678 and `SELECT extname FROM pg_extension` in the `vectors` db lists
`vector`.

- [x] Directory tree scaffolded with placeholders
- [x] `docker-compose.yml`: postgres (pgvector/pgvector:pg16) + n8n, healthcheck-gated
- [x] `db/init/01-databases.sql` creates `n8n` + `vectors` databases, enables pgvector
- [x] `.env.example` with every variable documented
- [x] `Makefile`: up, down, logs, ps, reset (reset confirms before dropping volumes)
- [x] `CLAUDE.md` and `PLAN.md` written
- [x] git initialized, `.gitignore` in place, first commit
- [x] `make up` verified: both containers healthy, pgvector extension confirmed present
      (pgvector 0.8.6 in the `vectors` db; n8n responds `HTTP 200` on :5678)

## M1 — Schema and ingestion

Vector schema (`db/init/02-schema.sql`, `documents` + `chunks` tables, `tenant` column
from day one, HNSW cosine index), then an n8n workflow that reads `corpus/sample/`,
chunks, embeds, and upserts. Re-ingestion is cheap via `content_sha` (hash the file,
skip if unchanged).

**Done when:** running the ingest workflow on `corpus/sample/` twice produces the same
chunk count the second time and re-embeds nothing, and `scripts/ingest_check.py` reports
chunk counts and confirms every embedding is 1536-dimensional.

- [ ] `db/init/02-schema.sql`
- [ ] Sample corpus committed to `corpus/sample/`
- [ ] Ingestion workflow (n8n), exported to `workflows/`
- [ ] `scripts/ingest_check.py` implemented
- [ ] Idempotent re-ingestion verified

## M2 — Retrieval and chat

Webhook-triggered workflow: embed the question, cosine-search top-k chunks, assemble a
prompt with numbered sources, call the model, return `{answer, sources[], usage}`.

Must include:
- A relevance floor (`RELEVANCE_THRESHOLD`) — below it, refuse instead of guessing.
- Every claim carries a source index mapping to a real chunk.

**Done when:** the webhook answers a question from the sample corpus with correct
citations, and returns the refusal for a question the corpus doesn't cover.

- [ ] Chat/retrieval workflow (n8n), exported to `workflows/`
- [ ] Relevance-floor refusal verified
- [ ] Citation mapping verified

## M3 — Eval harness

`eval/golden.yaml`: 20-30 question/expected-source/expected-answer triples over the
sample corpus, including at least 5 that should be refused.

`scripts/eval.py` scores:
- **Retrieval hit rate** — expected source in top-k?
- **Faithfulness** — LLM judge: is the answer supported by retrieved chunks only?
- **Refusal accuracy** — refused exactly the ones it should have?

Writes timestamped JSON + markdown to `eval/results/`.

**Done when:** `make eval` produces a report with three numbers — the baseline to
improve on.

- [ ] `eval/golden.yaml` populated (20-30 questions, 5+ refusals)
- [ ] `scripts/eval.py` implemented
- [ ] `make eval` target added
- [ ] Baseline report recorded in `eval/results/`

## M4 — Tuning

Chunk size/overlap, k, a keyword/BM25 pass alongside vector search, reranking, query
rewriting. Re-run `make eval` after each change.

**Done when:** every baseline number has improved, and the table below shows what did
it.

- [ ] Tuning experiments run, each re-scored with `make eval`

| Change | Retrieval hit rate | Faithfulness | Refusal accuracy |
|---|---|---|---|
| baseline (M3) | — | — | — |

## M5 — Hardening

- [ ] Error branch on every external call; retry with backoff on 429/5xx
- [ ] Dead-letter path for failed ingestions (table with the error, not the void)
- [ ] Cost logging: tokens in/out per request → `usage` table
- [ ] Rate limit + shared-secret header on the public webhook
- [ ] `/health` workflow: checks Postgres + model API, returns status

**Done when:** killing the Postgres container mid-ingest produces a logged, recoverable
failure instead of a half-written corpus.

## M6 — Demo UI and case study

- [ ] `ui/index.html`: chat transcript, expandable citations, latency + token cost shown
      per answer
- [ ] `README.md` written as a buyer-facing case study: problem, architecture diagram,
      eval numbers before/after, monthly running cost, corpus onboarding time

**Done when:** clone → `make up` → `make ingest` → `make eval` → open the UI → full demo
in under ten minutes, no explanation of what n8n is.

## M7 (later) — The multi-tenant seam

Namespace ingestion and retrieval by `tenant`, one credential set per tenant, one
workflow. This is the step that needs the n8n embed/commercial licensing conversation,
since it means one instance serving multiple customers.

- [ ] Tenant-scoped ingestion
- [ ] Tenant-scoped retrieval
- [ ] Per-tenant credentials
- [ ] Licensing conversation with n8n resolved
