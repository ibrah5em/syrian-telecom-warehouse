"""Extract Syriatel OLTP tables into pandas DataFrames."""
from __future__ import annotations

from datetime import date

import pandas as pd
import psycopg

from etl.config import settings
from etl.utils.logging import get_logger

logger = get_logger(__name__)

_CUSTOMERS_SQL = """
SELECT
    c.customer_id::text AS customer_id,
    c.full_name,
    c.phone,
    ci.city_ar,
    c.signup_date::date AS signup_date
FROM customers c
JOIN cities ci ON ci.city_id = c.city_id
ORDER BY c.customer_id
"""

_PRODUCTS_SQL = """
SELECT
    product_id::text AS product_id,
    product_name,
    category,
    unit_price
FROM products
ORDER BY product_id
"""

_ORDERS_SQL = """
SELECT
    o.order_id::text      AS order_id,
    o.customer_id::text   AS customer_id,
    o.product_id::text    AS product_id,
    o.quantity,
    o.unit_price_at_sale,
    o.total_price,
    o.order_date::date    AS order_date
FROM orders o
{where_clause}
ORDER BY o.order_date, o.order_id
"""


def _run_query(conn: psycopg.Connection, sql: str, params: dict | None = None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


def extract(since: date | None = None) -> dict[str, pd.DataFrame]:
    """Extract customers, products, and orders from Syriatel OLTP.

    Args:
        since: If set, restrict orders to order_date >= since.
               Customers and products are always fully extracted.
    """
    where = "WHERE o.order_date >= %(since)s" if since else ""
    orders_sql = _ORDERS_SQL.format(where_clause=where)
    params = {"since": since} if since else None

    with psycopg.connect(settings.syriatel.conninfo()) as conn:
        customers = _run_query(conn, _CUSTOMERS_SQL)
        products  = _run_query(conn, _PRODUCTS_SQL)
        orders    = _run_query(conn, orders_sql, params)

    logger.info(
        "extract.syriatel: %d customers, %d products, %d orders",
        len(customers), len(products), len(orders),
    )
    return {"customers": customers, "products": products, "orders": orders}
