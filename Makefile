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
