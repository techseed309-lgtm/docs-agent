# NOTE: this repo's parent folder has a space in its path on at least one dev
# machine. GNU Make has no way to quote a space inside its list functions
# ($(wildcard), $(words), $(word), prerequisite lists) or $(CURDIR) — it silently
# mis-splits them (verified). Rule for every target in this file: never build a
# file list or absolute path with Make's own functions; only use relative paths
# and let the shell (which quotes correctly) or Python (argv lists, pathlib) do
# any path handling. See CLAUDE.md "Environment notes".

.PHONY: up down logs ps reset

up:
	docker compose up -d
	@echo "n8n starting at http://localhost:5678 (give it a few seconds on first boot)"

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

# Drops both named volumes (postgres data + n8n data). Confirms before doing it —
# this is the one target here that destroys data.
reset:
	@echo "This will stop the stack and DELETE all Postgres and n8n data (named volumes)."
	@read -p "Type 'yes' to continue: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker compose down -v; \
		echo "Volumes removed."; \
	else \
		echo "Aborted, nothing removed."; \
	fi
