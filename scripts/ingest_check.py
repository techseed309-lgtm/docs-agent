#!/usr/bin/env python3
"""Sanity-check the vector store: chunk counts per document and embedding dimensions.

Used after running the ingestion workflow to confirm it did what it claims -- right
number of chunks, every embedding EXPECTED_DIM-dimensional (see below; matches
db/init/02-schema.sql) -- without opening a SQL client by hand.

Usage:
    python scripts/ingest_check.py
    python scripts/ingest_check.py --tenant default

Requires (from .env): VECTORS_DB_HOST, VECTORS_DB_PORT, VECTORS_DB_NAME,
VECTORS_DB_USER, VECTORS_DB_PASSWORD.
"""
import argparse
import os
import sys

# Matches db/init/02-schema.sql's VECTOR(768) -- nomic-embed-text's output width,
# not OpenAI's 1536. Change both together if the embedding model ever changes.
EXPECTED_DIM = 768

try:
    import psycopg2
except ImportError:
    sys.exit(
        "Missing dependency: psycopg2-binary. Install with:\n"
        "  python -m pip install -r scripts/requirements.txt"
    )


def load_dotenv_if_present(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def require_env(*names: str) -> dict:
    load_dotenv_if_present()
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Copy .env.example to .env and fill them in."
        )
    return {n: os.environ[n] for n in names}


def connect(env: dict):
    try:
        return psycopg2.connect(
            host=env["VECTORS_DB_HOST"],
            port=env["VECTORS_DB_PORT"],
            dbname=env["VECTORS_DB_NAME"],
            user=env["VECTORS_DB_USER"],
            password=env["VECTORS_DB_PASSWORD"],
        )
    except psycopg2.OperationalError as e:
        sys.exit(f"Could not connect to the vectors database: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", default=None, help="Restrict to one tenant (default: show all)")
    args = parser.parse_args()

    env = require_env(
        "VECTORS_DB_HOST", "VECTORS_DB_PORT", "VECTORS_DB_NAME",
        "VECTORS_DB_USER", "VECTORS_DB_PASSWORD",
    )

    conn = connect(env)
    try:
        with conn.cursor() as cur:
            tenant_filter = ""
            params: tuple = ()
            if args.tenant:
                tenant_filter = "WHERE d.tenant = %s"
                params = (args.tenant,)

            cur.execute(
                f"""
                SELECT d.id, d.tenant, d.source_path, d.title, d.content_sha,
                       d.ingested_at, COUNT(c.id) AS chunk_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                {tenant_filter}
                GROUP BY d.id
                ORDER BY d.source_path
                """,
                params,
            )
            rows = cur.fetchall()

            if not rows:
                print("No documents ingested yet.")
                return

            total_chunks = 0
            print(f"{'source_path':<45} {'chunks':>7}  content_sha")
            print("-" * 80)
            for _id, tenant, source_path, title, content_sha, ingested_at, chunk_count in rows:
                total_chunks += chunk_count
                print(f"{source_path:<45} {chunk_count:>7}  {content_sha[:12]}...")
            print("-" * 80)
            print(f"{len(rows)} document(s), {total_chunks} chunk(s) total")

            # Embedding dimension check -- every row in chunks is declared VECTOR(1536)
            # by the schema itself, so a mismatched width can't be silently inserted;
            # this confirms none were skipped some other way (e.g. a NULL/zero vector).
            cur.execute(
                """
                SELECT vector_dims(c.embedding), COUNT(*)
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                {tenant_filter}
                GROUP BY 1
                ORDER BY 1
                """.replace("{tenant_filter}", tenant_filter.replace("d.tenant", "d.tenant") if args.tenant else ""),
                params,
            )
            dim_rows = cur.fetchall()
            bad = [d for d in dim_rows if d[0] != EXPECTED_DIM]
            if bad:
                print("\nEMBEDDING DIMENSION MISMATCH:")
                for dim, count in dim_rows:
                    print(f"  dim={dim}: {count} chunk(s)")
                sys.exit(1)
            else:
                dim = dim_rows[0][0] if dim_rows else "n/a"
                print(f"All embeddings confirmed {dim}-dimensional.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
