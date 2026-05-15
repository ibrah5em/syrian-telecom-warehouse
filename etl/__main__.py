"""
ETL entrypoint.

Usage:
    python -m etl                       # incremental since previous Sunday 02:00 UTC
    python -m etl --since 2025-01-01    # incremental from explicit date
    python -m etl --full                # full reload
    python -m etl --dry-run             # extract + transform only, skip load

Pipeline stages:
    1. EXTRACT   — read customers/products/orders from each OLTP
    2. TRANSFORM — normalize phones, map cities, compute MTN totals, validate Syriatel totals
    3. LOAD DIMS — upsert dim_customer, dim_product; receive surrogate-key maps
    4. TRANSFORM SALES — resolve natural keys to SK, build fact_sales rows
    5. LOAD FACTS — insert fact_sales (ON CONFLICT DO NOTHING for idempotency)
    6. AUDIT     — close run record; write quarantine rows to etl_errors
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

from etl.config import settings
from etl.utils.logging import get_logger

logger = get_logger(__name__)


def previous_sunday_02utc(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    days_since_sunday = (now.weekday() + 1) % 7
    sunday = (now - timedelta(days=days_since_sunday)).replace(
        hour=2, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
    )
    if sunday > now:
        sunday -= timedelta(days=7)
    return sunday


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--since", type=date.fromisoformat,
                     help="Process orders on or after this date (YYYY-MM-DD)")
    grp.add_argument("--full", action="store_true",
                     help="Full reload — ignore --since")
    p.add_argument("--dry-run", action="store_true",
                   help="Extract + transform, do not load into DW")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    batch_id   = uuid.uuid4()
    started_at = datetime.now(timezone.utc)

    if args.full:
        since = None
        mode  = "FULL"
    elif args.since:
        since = args.since
        mode  = f"INCREMENTAL since {since}"
    else:
        since = previous_sunday_02utc().date()
        mode  = f"INCREMENTAL since {since} (default — previous Sunday)"

    logger.info("ETL batch %s starting — mode: %s, dry_run=%s", batch_id, mode, args.dry_run)

    from etl.load.audit import close_run, open_run, write_quarantine

    if not args.dry_run:
        open_run(batch_id, started_at)

    rows_extracted   = 0
    rows_loaded      = 0
    all_quarantine: list[dict] = []

    try:
        # ── EXTRACT ──────────────────────────────────────────────────────────
        from etl.extract.mtn      import extract as extract_mtn
        from etl.extract.syriatel import extract as extract_syr

        syr_data = extract_syr(since)
        mtn_data = extract_mtn(since)

        rows_extracted = (
            len(syr_data["customers"]) + len(syr_data["products"]) + len(syr_data["orders"])
            + len(mtn_data["clients"]) + len(mtn_data["items"]) + len(mtn_data["transactions"])
        )

        # ── TRANSFORM DIMS ───────────────────────────────────────────────────
        from etl.transform.customers import transform as transform_customers
        from etl.transform.products  import transform as transform_products

        cust_result = transform_customers(syr_data, mtn_data)
        prod_result = transform_products(syr_data, mtn_data)

        all_quarantine += cust_result.quarantine + prod_result.quarantine

        if args.dry_run:
            logger.info(
                "DRY RUN — skipping load. Would load %d customers, %d products; "
                "%d rows already quarantined.",
                len(cust_result.records), len(prod_result.records), len(all_quarantine),
            )
            finished_at = datetime.now(timezone.utc)
            elapsed = (finished_at - started_at).total_seconds()
            logger.info("ETL batch %s dry-run complete in %.2fs", batch_id, elapsed)
            return 0

        # ── LOAD DIMS ────────────────────────────────────────────────────────
        from etl.load.dims import get_company_sk_map, upsert_dim_customer, upsert_dim_product

        customer_sk_map = upsert_dim_customer(cust_result.records, batch_id)
        product_sk_map  = upsert_dim_product(prod_result.records, batch_id)
        company_sk_map  = get_company_sk_map()

        # ── TRANSFORM SALES ──────────────────────────────────────────────────
        from etl.transform.sales import transform as transform_sales

        sales_result = transform_sales(
            syr_data, mtn_data,
            customer_sk_map, product_sk_map, company_sk_map,
        )
        all_quarantine += sales_result.quarantine

        # ── LOAD FACTS ───────────────────────────────────────────────────────
        from etl.load.facts import insert_fact_sales

        rows_loaded = insert_fact_sales(sales_result.records, batch_id)

        # ── AUDIT ────────────────────────────────────────────────────────────
        write_quarantine(batch_id, all_quarantine)

        finished_at = datetime.now(timezone.utc)
        elapsed = (finished_at - started_at).total_seconds()

        close_run(
            batch_id, finished_at,
            rows_extracted, rows_loaded, len(all_quarantine),
            status="succeeded",
        )
        logger.info(
            "ETL batch %s complete in %.2fs: %d extracted, %d loaded, %d quarantined",
            batch_id, elapsed, rows_extracted, rows_loaded, len(all_quarantine),
        )
        return 0

    except Exception:
        logger.exception("ETL batch %s FAILED", batch_id)
        finished_at = datetime.now(timezone.utc)
        if not args.dry_run:
            try:
                close_run(
                    batch_id, finished_at,
                    rows_extracted, rows_loaded, len(all_quarantine),
                    status="failed",
                    notes="Unhandled exception — see logs",
                )
            except Exception:
                logger.exception("Failed to close ETL run record for batch %s", batch_id)
        return 1


if __name__ == "__main__":
    sys.exit(main())
