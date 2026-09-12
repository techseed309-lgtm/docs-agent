#!/usr/bin/env python3
"""Export and import n8n workflows via the n8n REST API.

Keeps workflows/*.json in this repo in sync with what's actually running in n8n,
so the JSON in git is the source of truth (per CLAUDE.md).

Credentials (the Postgres connection workflows use) are NOT stored in workflow
JSON -- n8n only ever stores a credential ID reference, and IDs are assigned
per-instance. A workflow exported from one n8n instance and imported into a
fresh one (a clean clone's first `make up`) would reference a credential ID
that doesn't exist there. `credentials` (below) closes that gap: it creates the
credential this repo's workflows expect, by name, idempotently -- and `import`
re-resolves every node's credential reference to whatever ID that name
currently has on the target instance, rather than trusting the ID baked into
the checked-in JSON.

Usage:
    python scripts/n8n_api.py credentials
    python scripts/n8n_api.py import --file workflows/01-ingest.json
    python scripts/n8n_api.py export --out workflows/
    python scripts/n8n_api.py export --out workflows/ --name "docs-agent: ingest" --file workflows/01-ingest.json

Requires (from .env): N8N_API_BASE_URL, N8N_API_KEY. `credentials` also needs
POSTGRES_USER, POSTGRES_PASSWORD.
Uses only the Python standard library (urllib) -- no HTTP client dependency needed
for a handful of simple JSON REST calls.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request


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
            f"Copy .env.example to .env and fill them in, and generate an n8n API "
            f"key under Settings > n8n API in the n8n UI."
        )
    return {n: os.environ[n] for n in names}


def api_request(base_url: str, api_key: str, method: str, path: str, body: dict = None):
    url = base_url.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-N8N-API-KEY", api_key)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        sys.exit(f"n8n API error {e.code} for {method} {path}: {detail}")
    except urllib.error.URLError as e:
        sys.exit(
            f"Could not reach n8n at {base_url}: {e.reason}. "
            f"Is the stack up (`make up`) and N8N_API_BASE_URL correct?"
        )


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "workflow"


def list_workflows(base_url: str, api_key: str) -> list:
    workflows = []
    cursor = None
    while True:
        path = "/api/v1/workflows" + (f"?cursor={cursor}" if cursor else "")
        page = api_request(base_url, api_key, "GET", path)
        workflows.extend(page.get("data", []))
        cursor = page.get("nextCursor")
        if not cursor:
            break
    return workflows


def list_credentials(base_url: str, api_key: str) -> list:
    return api_request(base_url, api_key, "GET", "/api/v1/credentials").get("data", [])


# name -> (n8n credential type, fields built from env in cmd_credentials)
REQUIRED_CREDENTIALS = ["Postgres (vectors)"]


def cmd_credentials(args: argparse.Namespace) -> None:
    env = require_env("N8N_API_BASE_URL", "N8N_API_KEY", "POSTGRES_USER", "POSTGRES_PASSWORD")
    base_url, api_key = env["N8N_API_BASE_URL"], env["N8N_API_KEY"]

    existing_by_name = {c["name"]: c for c in list_credentials(base_url, api_key)}

    wanted = {
        "Postgres (vectors)": {
            "type": "postgres",
            "data": {
                "host": "postgres",  # internal Docker network hostname, not localhost
                "port": 5432,
                "database": "vectors",
                "user": env["POSTGRES_USER"],
                "password": env["POSTGRES_PASSWORD"],
                "ssl": "disable",
            },
        },
    }

    for name, spec in wanted.items():
        if name in existing_by_name:
            print(f"Credential {name!r} already exists (id={existing_by_name[name]['id']}), leaving it as-is.")
            continue
        result = api_request(
            base_url, api_key, "POST", "/api/v1/credentials",
            {"name": name, "type": spec["type"], "data": spec["data"]},
        )
        print(f"Created credential {name!r} (id={result.get('id')})")


def cmd_export(args: argparse.Namespace) -> None:
    env = require_env("N8N_API_BASE_URL", "N8N_API_KEY")
    base_url, api_key = env["N8N_API_BASE_URL"], env["N8N_API_KEY"]

    workflows = list_workflows(base_url, api_key)
    if args.name:
        workflows = [w for w in workflows if w.get("name") == args.name]
        if not workflows:
            sys.exit(f"No workflow found with name {args.name!r}.")

    if not workflows:
        print("No workflows to export.")
        return

    os.makedirs(args.out, exist_ok=True)
    for w in workflows:
        full = api_request(base_url, api_key, "GET", f"/api/v1/workflows/{w['id']}")
        if args.file and len(workflows) == 1:
            out_path = args.file
        else:
            out_path = os.path.join(args.out, f"{slugify(w['name'])}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(full, f, indent=2, sort_keys=False)
            f.write("\n")
        print(f"Exported {w['name']!r} (id={w['id']}) -> {out_path}")


def cmd_import(args: argparse.Namespace) -> None:
    env = require_env("N8N_API_BASE_URL", "N8N_API_KEY")
    base_url, api_key = env["N8N_API_BASE_URL"], env["N8N_API_KEY"]

    if not os.path.exists(args.file):
        sys.exit(f"No such file: {args.file}")
    with open(args.file, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # n8n's create/update endpoints only accept a specific field set -- strip
    # server-managed fields (id, timestamps, etc.) that would otherwise cause a
    # validation error on import.
    allowed = {"name", "nodes", "connections", "settings", "staticData"}
    payload = {k: v for k, v in workflow.items() if k in allowed}
    payload.setdefault("settings", {})

    # Credential IDs in the checked-in JSON belong to whatever n8n instance last
    # exported it -- re-resolve every reference to this instance's current ID for
    # that credential NAME, or fail with a clear message (never silently import a
    # workflow pointing at a credential that doesn't exist here).
    creds_by_name = {c["name"]: c for c in list_credentials(base_url, api_key)}
    missing = set()
    for node in payload.get("nodes", []):
        for cred_type, ref in node.get("credentials", {}).items():
            name = ref.get("name")
            if name in creds_by_name:
                ref["id"] = creds_by_name[name]["id"]
            else:
                missing.add(name)
    if missing:
        sys.exit(
            f"Workflow references credential(s) not present on this n8n instance: "
            f"{', '.join(sorted(missing))}. Run `python scripts/n8n_api.py credentials` first."
        )

    existing = [w for w in list_workflows(base_url, api_key) if w.get("name") == payload.get("name")]
    if existing:
        wf_id = existing[0]["id"]
        result = api_request(base_url, api_key, "PUT", f"/api/v1/workflows/{wf_id}", payload)
        print(f"Updated existing workflow {payload.get('name')!r} (id={wf_id})")
    else:
        result = api_request(base_url, api_key, "POST", "/api/v1/workflows", payload)
        wf_id = result.get("id")
        print(f"Created workflow {payload.get('name')!r} (id={wf_id})")

    if not args.no_activate:
        api_request(base_url, api_key, "POST", f"/api/v1/workflows/{wf_id}/activate")
        print(f"Activated {payload.get('name')!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    export_p = sub.add_parser("export", help="Export workflow(s) from n8n to workflows/*.json")
    export_p.add_argument("--out", default="workflows/", help="Output directory (default: workflows/)")
    export_p.add_argument("--name", default=None, help="Export only the workflow with this exact name")
    export_p.add_argument("--file", default=None, help="Exact output filename (only used with --name, single match)")
    export_p.set_defaults(func=cmd_export)

    import_p = sub.add_parser("import", help="Create or update a workflow in n8n from a JSON file")
    import_p.add_argument("--file", required=True, help="Path to a workflow JSON file")
    import_p.add_argument("--no-activate", action="store_true", help="Don't activate the workflow after import")
    import_p.set_defaults(func=cmd_import)

    creds_p = sub.add_parser("credentials", help="Create the n8n credentials workflows in this repo expect (idempotent)")
    creds_p.set_defaults(func=cmd_credentials)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
