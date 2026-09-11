#!/usr/bin/env python3
"""Export and import n8n workflows via the n8n REST API.

Keeps workflows/*.json in this repo in sync with what's actually running in n8n,
so the JSON in git is the source of truth (per CLAUDE.md).

Status: scaffold only (Milestone 0). Export/import logic lands in Milestone 1
alongside the first real workflow.

Usage:
    python scripts/n8n_api.py export --out workflows/
    python scripts/n8n_api.py import --file workflows/ingest.json

Requires (from .env): N8N_API_BASE_URL, N8N_API_KEY.
"""
import argparse
import os
import sys


def load_dotenv_if_present(path: str = ".env") -> None:
    """Minimal .env loader — stdlib only, no python-dotenv dependency needed
    for a handful of KEY=VALUE lines."""
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


def cmd_export(args: argparse.Namespace) -> None:
    require_env("N8N_API_BASE_URL", "N8N_API_KEY")
    sys.exit("export is not implemented yet — arrives in Milestone 1.")


def cmd_import(args: argparse.Namespace) -> None:
    require_env("N8N_API_BASE_URL", "N8N_API_KEY")
    sys.exit("import is not implemented yet — arrives in Milestone 1.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    export_p = sub.add_parser("export", help="Export workflows from n8n to workflows/*.json")
    export_p.add_argument("--out", default="workflows/", help="Output directory (default: workflows/)")
    export_p.set_defaults(func=cmd_export)

    import_p = sub.add_parser("import", help="Import a workflow JSON file into n8n")
    import_p.add_argument("--file", required=True, help="Path to a workflow JSON file")
    import_p.set_defaults(func=cmd_import)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
