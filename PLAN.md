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

> Embedding model changed from the brief's OpenAI default to self-hosted Ollama
> (`nomic-embed-text`, 768-dim) partway through this milestone -- see CLAUDE.md
> "Environment notes". The dimension in "done when" above is stated as written in the
> original brief; actual verification below uses 768, matching `db/init/02-schema.sql`.

- [x] `db/init/02-schema.sql`
- [x] Sample corpus committed to `corpus/sample/`
- [x] Ingestion workflow (n8n), exported to `workflows/01-ingest.json`
- [x] `scripts/ingest_check.py` implemented
- [x] Idempotent re-ingestion verified

### M1 verification (2026-09-11/12, this dev machine)

**Workflow design** (`workflows/01-ingest.json`, 14 nodes): three triggers (manual,
daily schedule, and a webhook for on-demand re-runs) all feed one pipeline -- read PDFs
from `/data/corpus/sample` -> extract text -> hash + build document metadata -> check
existing `content_sha` in Postgres (a dummy-row `LEFT JOIN` guarantees exactly one row
back per document, changed or not) -> filter to only changed/new documents in a Code
node -> upsert `documents` row -> delete that document's old chunks -> chunk the text
-> loop over chunks one at a time (`Split In Batches`, batch size 1 -- Ollama on CPU
only has one processing slot; firing chunks concurrently made every request queue
behind the others until n8n's own timeout killed them, so throttling to strictly
sequential was the fix, not the HTTP node's own batching option, which turned out not
to throttle anything) -> embed via Ollama's `/api/embeddings` -> insert into `chunks`.

**Run 1** (execution id 6, clean database):
- Status: success
- Duration: 1h 20m 37s (22:10:36 -> 23:31:13 UTC) -- CPU-only local inference is the
  real tradeoff against $0 cost; worth stating plainly in the eventual case study.
- Result: 15 documents, **2848 chunks**, all confirmed 768-dimensional by
  `scripts/ingest_check.py`.
- ~852,230 total tokens processed (chunks.token_count sum; approximate, char-count
  based, not Ollama's own tokenizer count), avg 299 tokens/chunk.
- Cost: **$0** -- self-hosted embeddings, no API billed.

**Run 2** (execution id 8, same corpus, unchanged):
- Status: success
- Duration: **37 seconds** (vs. 1h20m for run 1)
- Result: chunk count unchanged at **2848**; document count unchanged at 15
- Confirmed via Ollama's own logs (`docker compose logs ollama`) that **zero**
  `/api/embeddings` requests were made in the run-2 time window -- not inferred from
  timing, checked directly.
- Cost: **$0** either way, but the token/compute savings from skipping unchanged
  documents is the real point `content_sha` buys.

**Bonus, unplanned but informative**: the daily Schedule Trigger fired on its own
(execution id 7) while run 1 was still mid-flight -- a genuine concurrency case, not
staged. It correctly saw all 15 documents as already-upserted-and-unchanged (documents
are upserted early, before the slow per-chunk embedding loop) and no-opped safely in 33s.
Known sharp edge for later: two runs racing on a document that's *actually* changed
(both deciding "needs reingest" and both deleting/reinserting its chunks concurrently)
isn't guarded against yet -- fine for a single-schedule production setup, worth a lock
or dedup key before M7's multi-tenant concurrency goes up.

**Real bugs found and fixed while building this** (kept here because "how it broke and
why" is exactly the kind of detail that reads as engineering rigor, not something to
tidy away):
1. Postgres node context: a plain `DELETE ... WHERE document_id = $1` with no
   `RETURNING` collapses to a *single* generic output item covering every input item's
   execution, not one item per input -- breaks downstream `pairedItem`/`itemMatching`
   with an ambiguous "Multiple matches" error the moment more than one document is in
   flight. Fixed by wrapping in a CTE with a bare `COUNT(*)` (no `GROUP BY`), which
   Postgres always returns as exactly one row.
2. Same root cause, worse case: an `INSERT ... ON CONFLICT DO UPDATE ... WHERE ...
   RETURNING` guard that's designed to return *zero* rows when content is unchanged
   collapses ALL-unchanged-item executions into one ambiguous item too -- discovered on
   the very first idempotency test (run 2 of the *first* workflow version errored
   instead of succeeding quietly). Fixed by moving the skip-decision out of SQL
   entirely: a `Check Existing` query that always returns exactly one row (dummy-row
   `LEFT JOIN`) plus an explicit JS `.filter()` in a Code node, and echoing every field
   downstream code needs through each SQL round-trip via `RETURNING`/`SELECT $n AS ...`
   rather than reaching back across node boundaries with `itemMatching`.
3. n8n's HTTP Request node `options.batching` did not actually throttle concurrent
   requests in this version (confirmed: ~10-12 embedding calls still fired at once,
   overloading Ollama's single CPU processing slot until they hit whatever timeout was
   configured). Fixed with the standard `Split In Batches` loop pattern instead, which
   did throttle correctly (verified in Ollama's own logs: clean sequential ~200-700ms
   requests, no more pile-ups).
4. Host port collisions (native Postgres on 5432, another project's Postgres on 5433) --
   see the M0 section above; surfaced again here since it's this milestone's DB work
   that actually exercised it.

### Post-M1 audit: does this actually survive a clean clone?

Asked to make M0/M1 "seamless to continue building over, production quality, no
placeholders" -- rather than assume the answer was yes, ran an actual
`make reset && make up && make import && make ingest` from nothing and found two
real bugs that everything up to this point had been masking:

1. **The workflow couldn't run on anyone else's instance.** It referenced a Postgres
   credential ID that only existed because I'd created it by hand via the n8n API
   earlier in this session. A genuinely clean clone's n8n has no such credential --
   the workflow would fail immediately. Fixed properly, not papered over: added
   `scripts/n8n_api.py credentials` (creates the credential idempotently, by name)
   and made `import` re-resolve every node's credential reference to whatever ID that
   name currently has on the target instance, rather than trusting the ID baked into
   the checked-in JSON. Wired into a new `make import` target.
2. **`db/init/02-schema.sql` silently never ran against the right database.** Each
   file in `docker-entrypoint-initdb.d` is its own `psql` invocation against
   `POSTGRES_DB` ("postgres") -- `01-databases.sql`'s `\c vectors` does not carry
   over to the next file. `documents` was quietly being created in the `postgres`
   database and `CREATE TABLE chunks` was failing outright (`type "vector" does not
   exist`, since pgvector was only enabled in `vectors`). This had been masked the
   entire time because the schema had only ever been applied by hand with
   `-d vectors` explicitly. Fixed by adding `\c vectors` to the top of the file,
   matching `01-databases.sql`'s own pattern.

Two smaller things fixed in the same pass:
- `make reset` was dropping `ollama_data` along with the actual state (Postgres/n8n)
  -- wasteful, since that's a ~2.3GB model cache with nothing precious in it, not
  something worth re-downloading on every reset. Now only drops `pgdata`/`n8n_data`.
- PDF-extracted text can contain NUL bytes, which Postgres `text` columns reject
  outright. None of the 15 NIST PDFs happened to trigger it, but the next corpus
  swap could have. Stripped in `Prepare Document` before hashing/storing.

Also cleaned up: an orphaned unused credential (Ollama needs no auth, so the
`ollamaApi` credential created early on was dead weight), two nodes that were
literally stacked on identical canvas coordinates, several others cramped from an
earlier redesign, and added three sticky notes in the workflow itself explaining the
trigger options, the dedup logic, and why the embedding loop is deliberately
sequential -- so the canvas explains itself to whoever opens it next.

**Re-verified after fixing, from actual nothing** (not re-asserted): `make reset`
(confirmed only `pgdata`/`n8n_data` dropped, Ollama models survived) -> `make up` ->
schema tables landed in the `vectors` database automatically, no manual `psql`
needed -> n8n's owner account recreated via UI (the one step with no API path, by
n8n's own design) -> `make import` (fresh credential created, fresh workflow created,
credential reference correctly resolved to the new ID) -> `make ingest` -> **identical
result**: 15 documents, 2848 chunks, same per-document counts, same `content_sha`
values as every prior run. 1h00m33s this time (CPU inference time varies run to run;
not a regression).

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
