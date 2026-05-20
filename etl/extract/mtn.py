"""Extract MTN Syria OLTP tables into pandas DataFrames."""
from __future__ import annotations

from datetime import date

import pandas as pd
import psycopg

from etl.config import settings
from etl.utils.logging import get_logger

logger = get_logger(__name__)

_CLIENTS_SQL = """
SELECT
    client_id::text  AS client_id,
    client_name,
    msisdn,
    city_en,
    registered_at::date AS registered_at
FROM clients
ORDER BY inserted_ts
"""

_ITEMS_SQL = """
SELECT
    item_id::text AS item_id,
    item_name,
    item_type,
    price_syp
FROM items
ORDER BY item_id
"""

_TX_SQL = """
SELECT
    tx_id::text     AS tx_id,
    client_id::text AS client_id,
    item_id::text   AS item_id,
    qty,
    price_at_tx,
    tx_date,
    tx_time
FROM transactions
{where_clause}
ORDER BY tx_date, tx_id
"""


def _run_query(conn: psycopg.Connection, sql: str, params: dict | None = None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


def extract(since: date | None = None) -> dict[str, pd.DataFrame]:
    """Extract clients, items, and transactions from MTN Syria OLTP.

    Args:
        since: If set, restrict transactions to tx_date >= since.
               Clients and items are always fully extracted.
    """
    where = "WHERE tx_date >= %(since)s" if since else ""
    tx_sql = _TX_SQL.format(where_clause=where)
    params = {"since": since} if since else None

    with psycopg.connect(settings.mtn.conninfo()) as conn:
        clients      = _run_query(conn, _CLIENTS_SQL)
        items        = _run_query(conn, _ITEMS_SQL)
        transactions = _run_query(conn, tx_sql, params)

    logger.info(
        "extract.mtn: %d clients, %d items, %d transactions",
        len(clients), len(items), len(transactions),
    )
    return {"clients": clients, "items": items, "transactions": transactions}
