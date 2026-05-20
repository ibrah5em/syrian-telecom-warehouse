"""Insert fact_sales rows.

Idempotency: ON CONFLICT (company_sk, source_order_id) DO NOTHING.
Re-running the pipeline for the same date range is safe — existing rows
are skipped, no duplicates are created.
"""
from __future__ import annotations

import uuid

import pandas as pd
import psycopg

from etl.config import settings
from etl.utils.logging import get_logger

logger = get_logger(__name__)

_INSERT_SQL = """
INSERT INTO dw.fact_sales
    (date_sk, customer_sk, product_sk, company_sk,
     quantity, unit_price_syp, total_amount_syp,
     source_order_id, etl_loaded_at, etl_batch_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
ON CONFLICT (company_sk, source_order_id) DO NOTHING
"""


def insert_fact_sales(records: pd.DataFrame, batch_id: uuid.UUID) -> int:
    """Bulk-insert fact_sales rows.

    Returns the number of rows actually inserted (conflicts excluded).
    """
    if records.empty:
        logger.info("load.fact_sales: no rows to insert")
        return 0

    rows = [
        (
            int(r.date_sk),
            int(r.customer_sk),
            int(r.product_sk),
            int(r.company_sk),
            int(r.quantity),
            float(r.unit_price_syp),
            float(r.total_amount_syp),
            str(r.source_order_id),
            str(batch_id),
        )
        for r in records.itertuples(index=False)
    ]

    with psycopg.connect(settings.dw.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.executemany(_INSERT_SQL, rows)
            # rowcount = sum of affected rows; ON CONFLICT DO NOTHING yields 0 per conflict
            newly_inserted = cur.rowcount if cur.rowcount >= 0 else len(rows)

    logger.info(
        "load.fact_sales: %d submitted, %d inserted (rest already existed)",
        len(rows), newly_inserted,
    )
    return newly_inserted
