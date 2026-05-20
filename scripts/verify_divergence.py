#!/usr/bin/env python3
"""
verify_divergence.py — Inspect both OLTP schemas via information_schema and
assert all 9 divergence dimensions from .claude/skills/oltp-divergence/SKILL.md.

Exits 0 on full pass, 1 if any dimension fails.

Run via:  python scripts/verify_divergence.py
Or via:   /verify-divergence (slash command)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install 'psycopg[binary]'", file=sys.stderr)
    sys.exit(2)


# ---- Connection -------------------------------------------------------------

def conn_syriatel():
    return psycopg.connect(
        host=os.getenv("SYRIATEL_HOST", "localhost"),
        port=int(os.getenv("SYRIATEL_PORT", "5433")),
        dbname=os.getenv("SYRIATEL_DB", "syriatel_oltp"),
        user=os.getenv("SYRIATEL_USER", "syriatel"),
        password=os.getenv("SYRIATEL_PASSWORD", "syriatel"),
    )


def conn_mtn():
    return psycopg.connect(
        host=os.getenv("MTN_HOST", "localhost"),
        port=int(os.getenv("MTN_PORT", "5434")),
        dbname=os.getenv("MTN_DB", "mtn_oltp"),
        user=os.getenv("MTN_USER", "mtn"),
        password=os.getenv("MTN_PASSWORD", "mtn"),
    )


# ---- Check framework --------------------------------------------------------

@dataclass
class Check:
    n: int
    name: str
    fn: Callable[[psycopg.Connection, psycopg.Connection], tuple[bool, str, str]]


def fetch(conn, sql, *params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetchone(conn, sql, *params):
    rows = fetch(conn, sql, *params)
    return rows[0] if rows else None


# ---- The 9 dimension checks -------------------------------------------------

def check_1_table_naming(syr, mtn):
    syr_tables = {r[0] for r in fetch(syr,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'")}
    mtn_tables = {r[0] for r in fetch(mtn,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'")}
    syr_has = {"customers", "products", "orders"} <= syr_tables
    mtn_has = {"clients", "items", "transactions"} <= mtn_tables
    ok = syr_has and mtn_has and syr_tables.isdisjoint({"clients","items","transactions"}) \
         and mtn_tables.isdisjoint({"customers","products","orders"})
    return ok, f"tables={sorted(syr_tables)}", f"tables={sorted(mtn_tables)}"


def check_2_pk_type(syr, mtn):
    syr_pk_type = fetchone(syr,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name='customers' AND column_name='customer_id'")
    mtn_pk_type = fetchone(mtn,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name='clients' AND column_name='client_id'")
    syr_t = syr_pk_type[0] if syr_pk_type else None
    mtn_t = mtn_pk_type[0] if mtn_pk_type else None
    ok = (syr_t == "integer") and (mtn_t == "uuid")
    return ok, f"customer_id is {syr_t}", f"client_id is {mtn_t}"


def check_3_city_language(syr, mtn):
    # Syriatel: cities table with city_ar column. MTN: city_en column on clients.
    syr_col = fetchone(syr,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='cities' AND column_name='city_ar'")
    mtn_col = fetchone(mtn,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='clients' AND column_name='city_en'")
    ok = (syr_col is not None) and (mtn_col is not None)
    return ok, "cities.city_ar exists" if syr_col else "cities.city_ar MISSING", \
              "clients.city_en exists" if mtn_col else "clients.city_en MISSING"


def check_4_phone_format(syr, mtn):
    # Check CHECK constraints for the regex pattern
    syr_chk = fetchone(syr,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname='chk_phone_e164'")
    mtn_chk = fetchone(mtn,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname='chk_msisdn_national'")
    syr_ok = syr_chk is not None and "+9639" in syr_chk[0]
    mtn_ok = mtn_chk is not None and "09" in mtn_chk[0]
    return (syr_ok and mtn_ok), \
        f"E.164 check: {syr_chk[0] if syr_chk else 'MISSING'}", \
        f"national check: {mtn_chk[0] if mtn_chk else 'MISSING'}"


def check_5_price_type(syr, mtn):
    syr_t = fetchone(syr,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name='products' AND column_name='unit_price'")
    mtn_t = fetchone(mtn,
        "SELECT data_type, numeric_precision, numeric_scale FROM information_schema.columns "
        "WHERE table_name='items' AND column_name='price_syp'")
    syr_ok = syr_t and syr_t[0] == "integer"
    mtn_ok = mtn_t and mtn_t[0] == "numeric" and mtn_t[1] == 12 and mtn_t[2] == 2
    return (syr_ok and mtn_ok), \
        f"unit_price={syr_t[0] if syr_t else None}", \
        f"price_syp=numeric({mtn_t[1]},{mtn_t[2]})" if mtn_t else "price_syp MISSING"


def check_6_order_total_storage(syr, mtn):
    # Syriatel: orders has total_price. MTN: transactions has NO total column.
    syr_has = fetchone(syr,
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='orders' AND column_name='total_price'")
    mtn_has = fetchone(mtn,
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='transactions' AND column_name IN ('total','total_amount','tx_total')")
    ok = (syr_has is not None) and (mtn_has is None)
    return ok, "orders.total_price stored" if syr_has else "orders.total_price MISSING", \
              "transactions has NO total column (good)" if mtn_has is None else "transactions has total column (BAD)"


def check_7_date_storage(syr, mtn):
    # Syriatel: orders.order_date is TIMESTAMP. MTN: transactions has tx_date (DATE) + tx_time (TIME).
    syr_t = fetchone(syr,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name='orders' AND column_name='order_date'")
    mtn_date = fetchone(mtn,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name='transactions' AND column_name='tx_date'")
    mtn_time = fetchone(mtn,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name='transactions' AND column_name='tx_time'")
    syr_ok = syr_t and "timestamp" in syr_t[0]
    mtn_ok = mtn_date and mtn_date[0] == "date" and mtn_time and mtn_time[0] == "time without time zone"
    return (syr_ok and mtn_ok), \
        f"order_date is {syr_t[0] if syr_t else None}", \
        f"tx_date={mtn_date[0] if mtn_date else None}, tx_time={mtn_time[0] if mtn_time else None}"


def check_8_category_case(syr, mtn):
    syr_chk = fetchone(syr,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='chk_category'")
    mtn_chk = fetchone(mtn,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='chk_item_type'")
    syr_ok = syr_chk and "'Internet'" in syr_chk[0] and "'INTERNET'" not in syr_chk[0]
    mtn_ok = mtn_chk and "'INTERNET'" in mtn_chk[0] and "'Internet'" not in mtn_chk[0]
    return (syr_ok and mtn_ok), \
        f"Title-case: {syr_chk[0] if syr_chk else 'MISSING'}", \
        f"UPPER-case: {mtn_chk[0] if mtn_chk else 'MISSING'}"


def check_9_product_name_language(syr, mtn):
    # Sample a product from each; check for Arabic vs ASCII script.
    syr_name = fetchone(syr, "SELECT product_name FROM products LIMIT 1")
    mtn_name = fetchone(mtn, "SELECT item_name FROM items LIMIT 1")
    if not syr_name or not mtn_name:
        return False, "no products seeded yet", "no items seeded yet"

    def is_arabic(s: str) -> bool:
        return any('\u0600' <= ch <= '\u06FF' for ch in s)

    syr_ok = is_arabic(syr_name[0])
    mtn_ok = not is_arabic(mtn_name[0]) and all(ord(ch) < 128 for ch in mtn_name[0])
    return (syr_ok and mtn_ok), \
        f"sample product_name={syr_name[0]!r} (Arabic={syr_ok})", \
        f"sample item_name={mtn_name[0]!r} (ASCII={mtn_ok})"


CHECKS = [
    Check(1, "Table naming",          check_1_table_naming),
    Check(2, "Primary key type",      check_2_pk_type),
    Check(3, "City language",         check_3_city_language),
    Check(4, "Phone format",          check_4_phone_format),
    Check(5, "Price type",            check_5_price_type),
    Check(6, "Order total storage",   check_6_order_total_storage),
    Check(7, "Date storage shape",    check_7_date_storage),
    Check(8, "Category case",         check_8_category_case),
    Check(9, "Product name language", check_9_product_name_language),
]


# ---- Main -------------------------------------------------------------------

def main() -> int:
    print("=" * 78)
    print("Divergence Verifier — Telecom DW")
    print("=" * 78)

    try:
        syr = conn_syriatel()
    except Exception as e:
        print(f"FAIL: cannot connect to Syriatel OLTP: {e}", file=sys.stderr)
        return 2
    try:
        mtn = conn_mtn()
    except Exception as e:
        print(f"FAIL: cannot connect to MTN OLTP: {e}", file=sys.stderr)
        return 2

    failures = 0
    for chk in CHECKS:
        try:
            ok, syr_detail, mtn_detail = chk.fn(syr, mtn)
        except Exception as e:
            ok = False
            syr_detail = mtn_detail = f"check raised: {e}"

        marker = "PASS" if ok else "FAIL"
        print(f"\n[{marker}] #{chk.n}: {chk.name}")
        print(f"   syriatel: {syr_detail}")
        print(f"   mtn:      {mtn_detail}")
        if not ok:
            failures += 1

    syr.close()
    mtn.close()

    print("\n" + "=" * 78)
    if failures:
        print(f"DIVERGENCE CHECK FAILED — {failures}/9 dimensions did not pass.")
        print("Fix the OLTP schemas (don't relax the verifier).")
        return 1
    print("DIVERGENCE CHECK PASSED — all 9 dimensions satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
