# NOTE: this repo's parent folder has a space in its path on at least one dev
# machine. GNU Make has no way to quote a space inside its list functions
# ($(wildcard), $(words), $(word), prerequisite lists) or $(CURDIR) — it silently
# mis-splits them (verified). Rule for every target in this file: never build a
# file list or absolute path with Make's own functions; only use relative paths
# and let the shell (which quotes correctly) or Python (argv lists, pathlib) do
# any path handling. See CLAUDE.md "Environment notes".

.PHONY: up down logs ps reset import export ingest eval

up:
	docker compose up -d
	@echo "n8n starting at http://localhost:5678 (give it a few seconds on first boot)"

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

# Creates the credentials workflows expect (idempotent, safe to re-run) and then
# imports + activates every workflow JSON in workflows/. This is what makes a
# clean clone's n8n instance actually match what's checked into git -- workflow
# JSON alone doesn't carry credentials (n8n only stores a per-instance ID
# reference), so `import` re-resolves those by name. See scripts/n8n_api.py.
import:
	python scripts/n8n_api.py credentials
	for f in workflows/*.json; do \
		python scripts/n8n_api.py import --file "$$f"; \
	done

# Pulls the current state of every workflow back out of n8n into workflows/*.json.
# Run this after editing a workflow in the n8n UI so the JSON in git stays the
# source of truth (per CLAUDE.md). Auto-names new workflows by slug; for the
# repo's numbered filenames (01-ingest.json, ...) re-run with --name/--file
# directly, e.g. `python scripts/n8n_api.py export --name "docs-agent: ingest" --file workflows/01-ingest.json`.
export:
	python scripts/n8n_api.py export --out workflows/

# Triggers the ingest workflow on demand via its webhook, instead of waiting for
# the daily schedule or opening the n8n UI.
ingest:
	@. ./.env; curl -s -X POST "http://localhost:$${N8N_PORT}/webhook/ingest-trigger" -w "\nHTTP %{http_code}\n"

# Runs eval/golden.yaml against the chat webhook and writes a scored report to
# eval/results/. Slow (each answered question is a real chat-model generation);
# that's the cost of a number you can trust over a vibe.
eval:
	python scripts/eval.py

# Drops the postgres + n8n volumes (all ingested data, n8n's workflows/credentials/
# owner account) -- but NOT ollama_data, deliberately: that's just a ~2.3GB model
# download cache, not state anyone wants to lose or wait to re-pull on every reset.
# (To nuke that too: `docker compose down -v` by hand.) Confirms before doing it --
# this is the one target here that destroys data.
reset:
	@echo "This will stop the stack and DELETE all Postgres and n8n data (not the Ollama model cache)."
	@read -p "Type 'yes' to continue: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker compose down; \
		docker volume rm docs-agent_pgdata docs-agent_n8n_data 2>/dev/null; \
		echo "Volumes removed (ollama_data kept)."; \
	else \
		echo "Aborted, nothing removed."; \
	fi
