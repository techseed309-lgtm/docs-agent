-- Runs once, automatically, the first time the postgres container starts against
-- an empty data volume (standard docker-entrypoint-initdb.d behavior).
--
-- Creates the two databases this stack needs out of one Postgres instance:
--   n8n     - n8n's own operational database (workflows, credentials, executions)
--   vectors - the RAG vector store (documents, chunks, embeddings; see 02-schema.sql)
--
-- Kept as a separate database from n8n's own, rather than a shared one, so the
-- vector store can be dumped/restored/reasoned about independently of n8n's
-- internal tables.

CREATE DATABASE n8n;
CREATE DATABASE vectors;

\c vectors
CREATE EXTENSION IF NOT EXISTS vector;
