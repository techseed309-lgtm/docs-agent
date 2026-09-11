#!/usr/bin/env python3
"""Sanity-check the vector store: chunk counts per document and embedding dimensions.

Used after running the ingestion workflow to confirm it did what it claims —
right number of chunks, every embedding the expected width — without opening
a SQL client by hand.

Status: scaffold only (Milestone 0). Real queries land in Milestone 1 once
db/init/02-schema.sql (documents/chunks tables) exists.

Usage:
    python scripts/ingest_check.py

Requires (from .env): VECTORS_DB_HOST, VECTORS_DB_PORT, VECTORS_DB_NAME,
VECTORS_DB_USER, VECTORS_DB_PASSWORD.
"""
import argparse
import os
import sys


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()

    require_env(
        "VECTORS_DB_HOST", "VECTORS_DB_PORT", "VECTORS_DB_NAME",
        "VECTORS_DB_USER", "VECTORS_DB_PASSWORD",
    )
    sys.exit("ingest_check is not implemented yet — arrives in Milestone 1, once the chunks table exists.")


if __name__ == "__main__":
    main()
