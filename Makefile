# Telecom DW — Makefile
# Use:  make help

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Load .env if present (for psql commands that don't go through Docker)
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Defaults (overridable by .env)
SYRIATEL_USER ?= syriatel
SYRIATEL_DB   ?= syriatel_oltp
MTN_USER      ?= mtn
MTN_DB        ?= mtn_oltp
DW_USER       ?= dw
DW_DB         ?= telecom_dw

# Python entrypoint — prefer the project venv if it exists, else system python3
PY ?= $(shell if [ -x ./venv/bin/python ]; then echo ./venv/bin/python; else echo python3; fi)

.PHONY: help up down restart wait-healthy schemas ping seed seed-reset etl etl-full \
        verify analytics dashboard dash-build dash-logs report listener-logs notify-test clean nuke

help:  ## Show this help
	@echo "Telecom DW — common commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up:  ## Start all containers (Syriatel, MTN, DW, Metabase)
	docker compose up -d

down:  ## Stop containers (keep data volumes)
	docker compose down

restart:  ## Restart containers
	docker compose restart

wait-healthy:  ## Wait until all three Postgres containers report healthy
	@echo "Waiting for healthy status..."
	@for i in $$(seq 1 30); do \
	  s=$$(docker inspect --format='{{.State.Health.Status}}' telecom_syriatel 2>/dev/null); \
	  m=$$(docker inspect --format='{{.State.Health.Status}}' telecom_mtn      2>/dev/null); \
	  d=$$(docker inspect --format='{{.State.Health.Status}}' telecom_dw       2>/dev/null); \
	  echo "  syriatel=$$s  mtn=$$m  dw=$$d"; \
	  if [ "$$s" = "healthy" ] && [ "$$m" = "healthy" ] && [ "$$d" = "healthy" ]; then \
	    echo "All healthy."; exit 0; \
	  fi; \
	  sleep 2; \
	done; \
	echo "Timed out waiting for healthy containers."; exit 1

schemas: wait-healthy  ## Apply OLTP and DW schemas (idempotent on first boot via initdb)
	@echo "Schemas are applied automatically via docker-entrypoint-initdb.d on first boot."
	@echo "If you've already booted, re-apply manually:"
	@echo "  docker exec -i telecom_syriatel psql -U $(SYRIATEL_USER) -d $(SYRIATEL_DB) < oltp/syriatel/schema.sql"
	@echo "  docker exec -i telecom_mtn      psql -U $(MTN_USER)      -d $(MTN_DB)      < oltp/mtn/schema.sql"
	@echo "  docker exec -i telecom_dw       psql -U $(DW_USER)       -d $(DW_DB)       < dw/schema.sql"
	@echo "  docker exec -i telecom_dw       psql -U $(DW_USER)       -d $(DW_DB)       < dw/cron.sql"

ping:  ## Smoke-check connectivity to all three Postgres instances
	@echo "Syriatel:"  && docker exec telecom_syriatel pg_isready -U $(SYRIATEL_USER) -d $(SYRIATEL_DB)
	@echo "MTN:"        && docker exec telecom_mtn      pg_isready -U $(MTN_USER)      -d $(MTN_DB)
	@echo "DW:"         && docker exec telecom_dw       pg_isready -U $(DW_USER)       -d $(DW_DB)

seed:  ## Seed both OLTPs with realistic test data (idempotent if empty)
	$(PY) scripts/seed_data.py --operator both

seed-reset:  ## TRUNCATE both OLTPs and reseed from scratch
	$(PY) scripts/seed_data.py --operator both --reset

verify:  ## Verify the 9-dimension divergence contract holds
	$(PY) scripts/verify_divergence.py

etl:  ## Run the ETL pipeline (incremental since last Sunday)
	$(PY) -m etl

etl-full:  ## Run the ETL pipeline (full reload)
	$(PY) -m etl --full

analytics:  ## Run the six analytical queries against the DW
	@for f in analytics/0*.sql; do \
	  echo "=== $$f ==="; \
	  docker exec -i telecom_dw psql -U $(DW_USER) -d $(DW_DB) < $$f; \
	done
	@echo "=== sanity ==="
	@docker exec -i telecom_dw psql -U $(DW_USER) -d $(DW_DB) < analytics/_sanity.sql

dashboard:  ## Configure Metabase dashboards (idempotent) and print URL
	python3 scripts/metabase_setup.py

dash-build:  ## Build and start the Plotly Dash analytics dashboard (port 8050)
	docker compose up -d --build dashboard
	@echo "Dashboard → http://localhost:8050"

dash-logs:  ## Tail the Dash dashboard container logs
	docker logs -f telecom_dashboard

metabase-url:  ## Print Metabase URLs (admin UI + public dashboard)
	@echo "Admin UI:  http://localhost:3000"
	@echo "Dashboard: http://localhost:3000/dashboard/2"
	@cat docs/metabase_setup.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('Public:   ', d.get('public_url','(not yet generated)'))" || true

report:  ## Build the Arabic PDF report (docs/report.pdf)
	pandoc docs/report.md \
	  -o docs/report.pdf \
	  --pdf-engine=xelatex \
	  -V mainfont="Amiri" \
	  -V geometry:margin=2cm \
	  -V dir=rtl \
	  -V lang=ar \
	  --toc

psql-syriatel:  ## Drop into psql against the Syriatel OLTP
	docker exec -it telecom_syriatel psql -U $(SYRIATEL_USER) -d $(SYRIATEL_DB)

psql-mtn:  ## Drop into psql against the MTN OLTP
	docker exec -it telecom_mtn psql -U $(MTN_USER) -d $(MTN_DB)

psql-dw:  ## Drop into psql against the DW
	docker exec -it telecom_dw psql -U $(DW_USER) -d $(DW_DB)

listener-logs:  ## Tail the ETL listener container logs
	docker logs -f telecom_etl_listener

notify-test:  ## Send a manual NOTIFY to trigger an ETL run via the listener
	docker exec telecom_dw psql -U $(DW_USER) -d $(DW_DB) -c "SELECT pg_notify('telecom_etl', 'manual-test');"

clean:  ## Stop containers and remove orphaned ones (keep volumes)
	docker compose down --remove-orphans

nuke:  ## DESTROY all data volumes — use with care
	@read -p "This deletes all DB data. Type 'yes' to proceed: " ans && [ "$$ans" = "yes" ]
	docker compose down -v
