"""Transform order/transaction data into fact_sales shape.

Divergence resolved here:
  - MTN total: computed as qty * price_at_tx (not stored in source)
  - Syriatel total: validated against quantity * unit_price_at_sale;
      mismatch rows are quarantined AND loaded with the recomputed value
  - Date storage: Syriatel TIMESTAMP / MTN (DATE + TIME) → date_sk (YYYYMMDD int)
  - Surrogate key resolution: natural keys → DW surrogate keys via sk_maps
"""
from __future__ import annotations

from datetime import date
from typing import NamedTuple

import pandas as pd

from etl.utils.logging import get_logger

logger = get_logger(__name__)

_FACT_COLS = [
    "date_sk", "customer_sk", "product_sk", "company_sk",
    "quantity", "unit_price_syp", "total_amount_syp", "source_order_id",
]


class SalesResult(NamedTuple):
    records: pd.DataFrame
    quarantine: list[dict]


def _date_to_sk(d: object) -> int:
    """Convert date-like value to YYYYMMDD integer."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return int(f"{d.year:04d}{d.month:02d}{d.day:02d}")  # type: ignore[union-attr]


def _transform_syriatel_orders(
    orders: pd.DataFrame,
    customer_sk_map: dict[tuple, int],
    product_sk_map: dict[tuple, int],
    company_sk: int,
) -> tuple[list[dict], list[dict]]:
    good: list[dict] = []
    bad: list[dict] = []
    for row in orders.itertuples(index=False):
        try:
            cust_sk = customer_sk_map.get(("SYRIATEL", str(row.customer_id)))
            if cust_sk is None:
                raise ValueError(f"no customer_sk for SYRIATEL customer_id={row.customer_id!r}")
            prod_sk = product_sk_map.get(("SYRIATEL", str(row.product_id)))
            if prod_sk is None:
                raise ValueError(f"no product_sk for SYRIATEL product_id={row.product_id!r}")

            computed = int(row.quantity) * int(row.unit_price_at_sale)
            stored   = int(row.total_price)

            if computed != stored:
                mismatch_reason = (
                    f"inconsistent_stored_total: stored={stored}, computed={computed}"
                )
                logger.warning(
                    "Syriatel order %s: stored total %d ≠ computed %d — using computed",
                    row.order_id, stored, computed,
                )
                bad.append({
                    "source_system": "SYRIATEL",
                    "source_table":  "orders",
                    "source_row":    dict(zip(orders.columns, row)),
                    "reason":        mismatch_reason,
                })

            good.append({
                "date_sk":         _date_to_sk(row.order_date),
                "customer_sk":     cust_sk,
                "product_sk":      prod_sk,
                "company_sk":      company_sk,
                "quantity":        int(row.quantity),
                "unit_price_syp":  float(row.unit_price_at_sale),
                "total_amount_syp": float(computed),
                "source_order_id": str(row.order_id),
            })
        except ValueError as exc:
            bad.append({
                "source_system": "SYRIATEL",
                "source_table":  "orders",
                "source_row":    dict(zip(orders.columns, row)),
                "reason":        str(exc),
            })
    return good, bad


def _transform_mtn_transactions(
    transactions: pd.DataFrame,
    customer_sk_map: dict[tuple, int],
    product_sk_map: dict[tuple, int],
    company_sk: int,
) -> tuple[list[dict], list[dict]]:
    good: list[dict] = []
    bad: list[dict] = []
    for row in transactions.itertuples(index=False):
        try:
            cust_sk = customer_sk_map.get(("MTN", str(row.client_id)))
            if cust_sk is None:
                raise ValueError(f"no customer_sk for MTN client_id={row.client_id!r}")
            prod_sk = product_sk_map.get(("MTN", str(row.item_id)))
            if prod_sk is None:
                raise ValueError(f"no product_sk for MTN item_id={row.item_id!r}")

            total = round(float(row.qty) * float(row.price_at_tx), 2)
            good.append({
                "date_sk":          _date_to_sk(row.tx_date),
                "customer_sk":      cust_sk,
                "product_sk":       prod_sk,
                "company_sk":       company_sk,
                "quantity":         int(row.qty),
                "unit_price_syp":   float(row.price_at_tx),
                "total_amount_syp": total,
                "source_order_id":  str(row.tx_id),
            })
        except ValueError as exc:
            bad.append({
                "source_system": "MTN",
                "source_table":  "transactions",
                "source_row":    dict(zip(transactions.columns, row)),
                "reason":        str(exc),
            })
    return good, bad


def transform(
    syr_data: dict,
    mtn_data: dict,
    customer_sk_map: dict[tuple, int],
    product_sk_map: dict[tuple, int],
    company_sk_map: dict[str, int],
) -> SalesResult:
    syr_good, syr_bad = _transform_syriatel_orders(
        syr_data["orders"],
        customer_sk_map,
        product_sk_map,
        company_sk_map["SYRIATEL"],
    )
    mtn_good, mtn_bad = _transform_mtn_transactions(
        mtn_data["transactions"],
        customer_sk_map,
        product_sk_map,
        company_sk_map["MTN"],
    )

    all_good = syr_good + mtn_good
    all_bad  = syr_bad  + mtn_bad

    logger.info(
        "transform.sales: %d ok, %d quarantined "
        "(syr: %d ok / %d bad  |  mtn: %d ok / %d bad)",
        len(all_good), len(all_bad),
        len(syr_good), len(syr_bad),
        len(mtn_good), len(mtn_bad),
    )

    return SalesResult(
        records=pd.DataFrame(all_good, columns=_FACT_COLS) if all_good else pd.DataFrame(columns=_FACT_COLS),
        quarantine=all_bad,
    )
