# Postgres 16 + pg_cron for the unified data warehouse.
FROM postgres:16

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-16-cron \
 && rm -rf /var/lib/apt/lists/*
