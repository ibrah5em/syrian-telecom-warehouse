"""Upsert dimension tables and return surrogate-key maps.

All upserts use ON CONFLICT DO UPDATE (SCD Type 1 — overwrite).
After each bulk upsert we SELECT the full SK map so fact_sales transform
can resolve natural keys regardless of whether they were new or existing.
"""
from __future__ import annotations

import uuid

import pandas as pd
import psycopg

from etl.config import settings
from etl.utils.logging import get_logger

logger = get_logger(__name__)

_UPSERT_CUSTOMER = """
INSERT INTO dw.dim_customer
    (source_system, source_customer_id, full_name, phone_e164,
     city, signup_date, etl_loaded_at, etl_batch_id)
VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
ON CONFLICT (source_system, source_customer_id) DO UPDATE SET
    full_name     = EXCLUDED.full_name,
    phone_e164    = EXCLUDED.phone_e164,
    city          = EXCLUDED.city,
    signup_date   = EXCLUDED.signup_date,
    etl_loaded_at = EXCLUDED.etl_loaded_at,
    etl_batch_id  = EXCLUDED.etl_batch_id
"""

_UPSERT_PRODUCT = """
INSERT INTO dw.dim_product
    (source_system, source_product_id, product_name_en,
     category, unit_price_syp, etl_loaded_at, etl_batch_id)
VALUES (%s, %s, %s, %s, %s, NOW(), %s)
ON CONFLICT (source_system, source_product_id) DO UPDATE SET
    product_name_en = EXCLUDED.product_name_en,
    category        = EXCLUDED.category,
    unit_price_syp  = EXCLUDED.unit_price_syp,
    etl_loaded_at   = EXCLUDED.etl_loaded_at,
    etl_batch_id    = EXCLUDED.etl_batch_id
"""


def upsert_dim_customer(records: pd.DataFrame, batch_id: uuid.UUID) -> dict[tuple, int]:
    """Upsert dim_customer; return {(source_system, source_customer_id) → customer_sk}."""
    if records.empty:
        logger.info("load.dim_customer: no rows to upsert")
        return {}

    rows = [
        (
            r.source_system, r.source_customer_id,
            r.full_name, r.phone_e164,
            r.city, r.signup_date, str(batch_id),
        )
        for r in records.itertuples(index=False)
    ]
    systems = list({r[0] for r in rows})

    with psycopg.connect(settings.dw.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM dw.dim_customer WHERE source_system = ANY(%s)",
                (systems,),
            )
            before = cur.fetchone()[0]

            cur.executemany(_UPSERT_CUSTOMER, rows)

            cur.execute(
                "SELECT COUNT(*) FROM dw.dim_customer WHERE source_system = ANY(%s)",
                (systems,),
            )
            after = cur.fetchone()[0]

            cur.execute(
                "SELECT source_system, source_customer_id, customer_sk "
                "FROM dw.dim_customer WHERE source_system = ANY(%s)",
                (systems,),
            )
            sk_map = {(r[0], r[1]): r[2] for r in cur.fetchall()}

    inserted = after - before
    updated  = len(rows) - inserted
    logger.info("load.dim_customer: %d inserted, %d updated", inserted, updated)
    return sk_map


def upsert_dim_product(records: pd.DataFrame, batch_id: uuid.UUID) -> dict[tuple, int]:
    """Upsert dim_product; return {(source_system, source_product_id) → product_sk}."""
    if records.empty:
        logger.info("load.dim_product: no rows to upsert")
        return {}

    rows = [
        (
            r.source_system, r.source_product_id,
            r.product_name_en, r.category,
            r.unit_price_syp, str(batch_id),
        )
        for r in records.itertuples(index=False)
    ]
    systems = list({r[0] for r in rows})

    with psycopg.connect(settings.dw.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM dw.dim_product WHERE source_system = ANY(%s)",
                (systems,),
            )
            before = cur.fetchone()[0]

            cur.executemany(_UPSERT_PRODUCT, rows)

            cur.execute(
                "SELECT COUNT(*) FROM dw.dim_product WHERE source_system = ANY(%s)",
                (systems,),
            )
            after = cur.fetchone()[0]

            cur.execute(
                "SELECT source_system, source_product_id, product_sk "
                "FROM dw.dim_product WHERE source_system = ANY(%s)",
                (systems,),
            )
            sk_map = {(r[0], r[1]): r[2] for r in cur.fetchall()}

    inserted = after - before
    updated  = len(rows) - inserted
    logger.info("load.dim_product: %d inserted, %d updated", inserted, updated)
    return sk_map


def get_company_sk_map() -> dict[str, int]:
    """Return {company_code → company_sk} from dim_company."""
    with psycopg.connect(settings.dw.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT company_code, company_sk FROM dw.dim_company")
            return {r[0]: r[1] for r in cur.fetchall()}
