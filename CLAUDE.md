# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A data warehouse consolidating two divergent Syrian telecom operators — Syriatel and MTN Syria — into a single star schema. The core problem is 9 systematic schema differences between the two OLTPs that the ETL pipeline must resolve.

**Stack:** Python 3.11+, PostgreSQL 16, pandas, psycopg, Docker Compose, Metabase, pg_cron

## Commands

### Environment Setup
```bash
cp .env.example .env
make up && make wait-healthy
pip install -r requirements.txt
make seed && make verify
```

### Common Make Targets
```bash
make up             # Start all 5 Docker services
make wait-healthy   # Block until all DBs are ready
make seed           # Generate 1000 customers + 10,000 orders per OLTP
make verify         # Assert all 9 divergence dimensions are present
make etl-full       # Full warehouse reload (idempotent)
make etl            # Incremental ETL since last Sunday 02:00 UTC
make analytics      # Run all 6 analytical SQL queries
make dashboard      # Configure Metabase at http://localhost:3000
make notify-test    # Manually trigger the ETL listener via pg_notify
```

### ETL CLI
```bash
python -m etl                     # Incremental (since previous Sunday 02:00 UTC)
python -m etl --since YYYY-MM-DD  # Explicit cutoff date
python -m etl --full              # Full reload
python -m etl --dry-run           # Extract + transform only, no DB writes
```

### Tests
```bash
python -m pytest etl/tests/ -v   # Run all tests
```

## Architecture

### Three-Tier Structure

```
Syriatel OLTP (port 5433)  ─┐
                              ├──► ETL Pipeline (Python) ──► Data Warehouse (port 5435) ──► Metabase (port 3000)
MTN OLTP (port 5434)       ─┘
```

The ETL runs as both a CLI (`python -m etl`) and a long-running listener container (`etl/listener.py`) that waits for `NOTIFY telecom_etl` from pg_cron (fires every Sunday 02:00 UTC).

### ETL Pipeline Stages (`etl/__main__.py`)

1. **Extract** (`etl/extract/`) — SQL queries to pandas DataFrames, respects `--since` cutoff
2. **Transform dims** (`etl/transform/customers.py`, `products.py`) — resolve all 9 divergences, bad rows → quarantine list
3. **Load dims** (`etl/load/dims.py`) — UPSERT using `(source_system, source_id)` as natural key; returns SK maps
4. **Transform facts** (`etl/transform/sales.py`) — resolve source IDs → surrogate keys, compute MTN totals, validate Syriatel totals
5. **Load facts** (`etl/load/facts.py`) — `INSERT ... ON CONFLICT (company_sk, source_order_id) DO NOTHING` (idempotency guarantee)
6. **Audit** (`etl/load/audit.py`) — write `etl_runs` row + quarantine rows to `etl_errors`; pipeline never crashes on bad data

### The 9-Dimension Divergence Contract

The central contract of this project. `make verify` asserts all 9 are present in the source schemas:

| # | Dimension | Syriatel | MTN | DW Resolution |
|---|-----------|----------|-----|---------------|
| 1 | Table names | customers/products/orders | clients/items/transactions | conformed dim_*/fact_* |
| 2 | Primary key | SERIAL int | UUID | surrogate `*_sk` SERIAL |
| 3 | City storage | Arabic (دمشق) | English (Damascus) | canonical English via `data/syrian_cities.csv` |
| 4 | Phone format | E.164 (+963944…) | National (0944…) | normalized to `+9639XXXXXXXX` |
| 5 | Price type | INTEGER | NUMERIC(12,2) | DW uses NUMERIC(14,2) |
| 6 | Order total | stored column | not stored | always present; computed for MTN, validated for Syriatel |
| 7 | Date storage | single TIMESTAMP | separate DATE + TIME | both → `date_sk` (YYYYMMDD int) |
| 8 | Product category | Title Case | UPPER | normalized to UPPER |
| 9 | Product names | Arabic | English | canonical English via `data/product_catalog.csv` |

### Warehouse Star Schema (`dw/schema.sql`)

- **`fact_sales`** — grain: one row per source order line; FKs to all dims; carries `source_order_id` for idempotency
- **`dim_customer`** — Type-1 SCD; natural key `(source_system, source_customer_id)`
- **`dim_product`** — Type-1 SCD; natural key `(source_system, source_product_id)`
- **`dim_date`** — populated at schema creation; `date_sk = YYYYMMDD` int
- **`dim_company`** — static; SYT and MTN rows seeded at init
- **`etl_runs`** / **`etl_errors`** — audit trail; errors stored as JSONB source row + reason

### Reference Data

- `data/syrian_cities.csv` — 17 cities, Arabic ↔ English mapping (used by `etl/utils/mappings.py`)
- `data/product_catalog.csv` — 15 offerings, Syriatel name ↔ MTN name + canonical English name + category

### Analytics Layer (`analytics/`)

Six SQL queries answering Ministry-of-Telecoms questions (revenue share, top customers, city breakdown, monthly trends, side-by-side KPIs, strategic indicators). `_sanity.sql` cross-validates Q1 and Q4 totals against raw fact counts.

Data mining in `analytics/mining/`: RFM quintile segmentation (`rfm_segment.py`) and Holt-Winters 3-month forecasting (`forecast.py`). Outputs go to `analytics/mining/output/`.

## Key Design Decisions

- **Idempotency:** `ON CONFLICT DO NOTHING` on `fact_sales` means any ETL run can be safely re-run. The CI pipeline explicitly verifies this (runs `etl-full` twice and checks row counts match).
- **Type-1 SCD only:** Dims overwrite on conflict. Ministry wants current state, not history.
- **Quarantine, don't crash:** Bad rows (unmapped city, phone normalization failure, total mismatch) are written to `etl_errors` and skipped — the pipeline always finishes.
- **LISTEN/NOTIFY decoupling:** pg_cron sends `NOTIFY telecom_etl`; the Python listener in the ETL container reacts. Manual trigger: `make notify-test`. Listener also auto-runs catch-up if last success > 8 days old.
- **Shared reference CSVs as truth:** Both OLTP transforms read from the same city/product CSVs, keeping mappings in one place.
