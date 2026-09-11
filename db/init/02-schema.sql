-- Vector store schema, in the `vectors` database (see 01-databases.sql).
--
-- tenant exists from day one on both tables, default 'default'. Unused until M7,
-- but it's the seam that turns this into a multi-tenant product later without a
-- migration -- see CLAUDE.md.
--
-- content_sha is what makes re-ingestion cheap: hash the file, skip it if
-- unchanged (M1 "done when" criterion).
--
-- VECTOR(768), not the brief's VECTOR(1536): a deliberate, explicit deviation.
-- The brief's default was OpenAI text-embedding-3-small (1536-dim); the project
-- switched to a fully self-hosted embedding model (Ollama nomic-embed-text,
-- 768-dim) for zero external API cost and zero data leaving the host. See
-- CLAUDE.md "Environment notes" for the full reasoning.

CREATE TABLE documents (
  id          BIGSERIAL PRIMARY KEY,
  tenant      TEXT NOT NULL DEFAULT 'default',
  source_path TEXT NOT NULL,
  title       TEXT,
  content_sha TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant, source_path)
);

CREATE TABLE chunks (
  id          BIGSERIAL PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  tenant      TEXT NOT NULL DEFAULT 'default',
  chunk_index INT NOT NULL,
  content     TEXT NOT NULL,
  token_count INT,
  embedding   VECTOR(768) NOT NULL
);

CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks (tenant);
