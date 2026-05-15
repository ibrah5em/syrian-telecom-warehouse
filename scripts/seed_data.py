#!/usr/bin/env python3
"""
seed_data.py — Generate realistic divergent Syrian telecom data for both OLTPs.

Usage:
    python scripts/seed_data.py --operator both
    python scripts/seed_data.py --operator syriatel --customers 500 --orders 5000
    python scripts/seed_data.py --operator mtn --reset
    python scripts/seed_data.py --operator both --seed 42 --days 365

Design notes:
- One synthetic "ground truth" population is generated, then projected differently
  into each OLTP — preserving the Divergence Rule from .claude/CLAUDE.md.
- Phone numbers, names, products are real-looking; cities use the canonical
  14-governorate list (with a few intentional unmapped ones for ETL quarantine).
- Deterministic given --seed.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install 'psycopg[binary]'", file=sys.stderr)
    sys.exit(2)


# ---- Reference data ----------------------------------------------------------

SYRIAN_CITIES = [
    ("دمشق",       "Damascus"),
    ("ريف دمشق",   "Rif Dimashq"),
    ("حلب",        "Aleppo"),
    ("حمص",        "Homs"),
    ("حماة",       "Hama"),
    ("اللاذقية",   "Latakia"),
    ("طرطوس",      "Tartus"),
    ("إدلب",       "Idlib"),
    ("الرقة",      "Raqqa"),
    ("دير الزور",  "Deir ez-Zor"),
    ("الحسكة",     "Al-Hasakah"),
    ("درعا",       "Daraa"),
    ("السويداء",   "As-Suwayda"),
    ("القنيطرة",   "Quneitra"),
]

# 3 unmapped districts — intentionally absent from city_mapping.csv
# so the ETL quarantine path is exercised
UNMAPPED_CITIES = [("جرمانا", None), ("صافيتا", None), ("سلمية", None)]

ARABIC_FIRST_NAMES = [
    "أحمد", "محمد", "علي", "عمر", "يوسف", "خالد", "حسن", "حسين", "إبراهيم", "مصطفى",
    "فاطمة", "عائشة", "مريم", "سارة", "ليلى", "نور", "رنا", "هدى", "زينب", "ريم",
    "بشار", "نزار", "وليد", "ماهر", "سامي", "كريم", "طارق", "سليمان", "أيمن", "باسل",
]
ARABIC_LAST_NAMES = [
    "الأحمد", "الحسن", "العلي", "الخطيب", "السيد", "المصري", "الحلبي", "الدمشقي",
    "العمر", "الزعبي", "الشامي", "الكردي", "الحمصي", "السوري", "الطرابلسي", "اللاذقاني",
    "الرفاعي", "البرازي", "العظمة", "القباني", "البيطار", "الجابري", "الكيلاني",
]

ENGLISH_FIRST_NAMES = [
    "Ahmad", "Mohammad", "Ali", "Omar", "Yousef", "Khaled", "Hassan", "Hussein",
    "Ibrahim", "Mustafa", "Fatima", "Aisha", "Maryam", "Sarah", "Layla", "Noor",
    "Rana", "Huda", "Zainab", "Reem", "Bashar", "Nizar", "Waleed", "Maher", "Sami",
]
ENGLISH_LAST_NAMES = [
    "Ahmad", "Hassan", "Ali", "Khatib", "Sayed", "Masri", "Halabi", "Dimashqi",
    "Omar", "Zoubi", "Shami", "Kurdi", "Homsi", "Souri", "Tarabulsi", "Rifai",
]

# (offering_id, category, syriatel_name_ar, syriatel_price_int, mtn_name_en, mtn_price_decimal)
PRODUCT_CATALOG = [
    (1,  "Internet", "باقة 1GB",             8000,  "INTERNET", "1GB Internet Bundle",    8000.00),
    (2,  "Internet", "باقة 5GB",             25000, "INTERNET", "5GB Internet Bundle",   25000.00),
    (3,  "Internet", "باقة 10GB",            45000, "INTERNET", "10GB Internet Bundle",  45000.00),
    (4,  "Internet", "باقة 20GB",            80000, "INTERNET", "20GB Internet Pack",    80000.00),
    (5,  "Internet", "باقة لا محدودة",       200000,"INTERNET", "Unlimited Internet",   200000.00),
    (6,  "Voice",    "دقائق 100",            5000,  "VOICE",    "100 Minutes Voice",     5000.00),
    (7,  "Voice",    "دقائق 500",            20000, "VOICE",    "500 Minutes Voice",    20000.00),
    (8,  "Voice",    "دقائق 1000",           35000, "VOICE",    "1000 Minutes Voice",   35000.00),
    (9,  "Voice",    "دقائق لا محدودة",      90000, "VOICE",    "Unlimited Voice",      90000.00),
    (10, "Bundle",   "باقة شاملة صغيرة",     30000, "BUNDLE",   "Small Combo Plan",     30000.00),
    (11, "Bundle",   "باقة شاملة متوسطة",    60000, "BUNDLE",   "Medium Combo Plan",    60000.00),
    (12, "Bundle",   "باقة شاملة كبيرة",     120000,"BUNDLE",   "Large Combo Plan",    120000.00),
    (13, "Bundle",   "باقة عائلية",          180000,"BUNDLE",   "Family Plan",         180000.00),
    (14, "Internet", "باقة ليلية 10GB",      18000, "INTERNET", "Night 10GB Pack",      18000.00),
    (15, "Voice",    "دقائق دولية 100",      50000, "VOICE",    "100 Intl Minutes",     50000.00),
]

MOBILE_PREFIXES = ["93", "94", "95", "98", "99"]


# ---- Generators --------------------------------------------------------------

def make_msisdn_9digit(rng: random.Random) -> str:
    """Generate the canonical 9-digit MSISDN: 9XXNNNNNN (Syrian mobile, 9 digits)."""
    prefix = rng.choice(MOBILE_PREFIXES)
    rest = "".join(rng.choices("0123456789", k=6))
    return f"9{prefix}{rest}"


def to_syriatel_phone(nine_digits: str) -> str:
    """Syriatel storage: +963XXXXXXXXX (E.164)."""
    return "+963" + nine_digits


def to_mtn_phone(nine_digits: str) -> str:
    """MTN storage: 0XXXXXXXXX (national)."""
    return "0" + nine_digits


def arabic_name(rng: random.Random) -> str:
    return f"{rng.choice(ARABIC_FIRST_NAMES)} {rng.choice(ARABIC_LAST_NAMES)}"


def english_name(rng: random.Random) -> str:
    return f"{rng.choice(ENGLISH_FIRST_NAMES)} {rng.choice(ENGLISH_LAST_NAMES)}"


def random_date(rng: random.Random, start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def random_time(rng: random.Random) -> time:
    return time(hour=rng.randint(0, 23), minute=rng.randint(0, 59), second=rng.randint(0, 59))


# ---- Seeding -----------------------------------------------------------------

@dataclass
class SeedConfig:
    operator: str
    customers: int
    products: int  # not really used — we always seed full catalog
    orders: int
    days: int
    seed: int
    reset: bool


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


def reset_syriatel(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE orders, customers, products, cities RESTART IDENTITY CASCADE")
    conn.commit()


def reset_mtn(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE transactions, clients, items RESTART IDENTITY CASCADE")
    conn.commit()


def seed_syriatel(cfg: SeedConfig, rng: random.Random) -> None:
    print(f"[syriatel] connecting...")
    conn = conn_syriatel()
    if cfg.reset:
        print(f"[syriatel] resetting...")
        reset_syriatel(conn)

    today = date.today()
    period_start = today - timedelta(days=cfg.days)

    with conn.cursor() as cur:
        # Cities (Arabic) — includes the 14 mapped + 3 unmapped
        all_cities = [a for a, _ in SYRIAN_CITIES] + [a for a, _ in UNMAPPED_CITIES]
        cur.executemany(
            "INSERT INTO cities (city_ar) VALUES (%s) ON CONFLICT (city_ar) DO NOTHING",
            [(c,) for c in all_cities],
        )
        cur.execute("SELECT city_id, city_ar FROM cities")
        city_rows = cur.fetchall()
        city_ids_mapped = [cid for cid, c in city_rows if c in [a for a, _ in SYRIAN_CITIES]]
        city_ids_unmapped = [cid for cid, c in city_rows if c in [a for a, _ in UNMAPPED_CITIES]]

        # Products (Arabic, Title case, INTEGER price)
        product_rows = [
            (s_name, s_cat, s_price)
            for (_, s_cat, s_name, s_price, _, _, _) in PRODUCT_CATALOG
        ]
        cur.executemany(
            "INSERT INTO products (product_name, category, unit_price) VALUES (%s, %s, %s)",
            product_rows,
        )
        cur.execute("SELECT product_id, unit_price FROM products")
        products = cur.fetchall()  # [(product_id, unit_price), ...]

        # Customers
        customer_rows = []
        used_phones = set()
        for _ in range(cfg.customers):
            while True:
                nine = make_msisdn_9digit(rng)
                phone = to_syriatel_phone(nine)
                if phone not in used_phones:
                    used_phones.add(phone)
                    break
            # 95% mapped cities, 5% unmapped (for ETL quarantine path)
            city_id = rng.choice(city_ids_mapped if rng.random() < 0.95 else city_ids_unmapped)
            name = arabic_name(rng)
            # Sprinkle whitespace artifacts on ~0.3% to exercise ETL trim
            if rng.random() < 0.003:
                name = "  " + name + " "
            signup = random_date(rng, period_start, today)
            customer_rows.append((name, phone, city_id, datetime.combine(signup, time(12, 0))))

        cur.executemany(
            "INSERT INTO customers (full_name, phone, city_id, signup_date) VALUES (%s, %s, %s, %s)",
            customer_rows,
        )
        cur.execute("SELECT customer_id FROM customers")
        customer_ids = [r[0] for r in cur.fetchall()]

        # Heavy users — 5% of customers get 5-10x order volume
        heavy_ids = set(rng.sample(customer_ids, k=max(1, len(customer_ids) // 20)))

        # Orders
        order_rows = []
        for _ in range(cfg.orders):
            cid = rng.choice(customer_ids)
            # Heavy users participate more often (oversample)
            if rng.random() < 0.30:
                cid = rng.choice(list(heavy_ids))
            pid, unit_price = rng.choice(products)
            qty = max(1, min(5, int(rng.gauss(1.2, 0.6))))
            total = qty * unit_price
            order_date = random_date(rng, period_start, today)
            order_ts = datetime.combine(order_date, random_time(rng))
            order_rows.append((cid, pid, qty, unit_price, total, order_ts))

        cur.executemany(
            "INSERT INTO orders (customer_id, product_id, quantity, unit_price_at_sale, total_price, order_date)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            order_rows,
        )

    conn.commit()
    conn.close()
    print(f"[syriatel] seeded: {len(customer_rows)} customers, {len(product_rows)} products, {len(order_rows)} orders")


def seed_mtn(cfg: SeedConfig, rng: random.Random) -> None:
    print(f"[mtn] connecting...")
    conn = conn_mtn()
    if cfg.reset:
        print(f"[mtn] resetting...")
        reset_mtn(conn)

    today = date.today()
    period_start = today - timedelta(days=cfg.days)

    with conn.cursor() as cur:
        # Items (English, UPPER case, NUMERIC price)
        item_rows = [
            (m_name, m_cat, m_price)
            for (_, _, _, _, m_cat, m_name, m_price) in PRODUCT_CATALOG
        ]
        cur.executemany(
            "INSERT INTO items (item_name, item_type, price_syp) VALUES (%s, %s, %s)",
            item_rows,
        )
        cur.execute("SELECT item_id, price_syp FROM items")
        items = cur.fetchall()  # [(uuid, price), ...]

        # Clients
        all_cities_en = [e for _, e in SYRIAN_CITIES]
        # MTN also has a few "non-standard" district strings — intentionally
        all_cities_en_with_unmapped = all_cities_en + ["Jaramana", "Safita", "Salamiyah"]

        client_rows = []
        used_msisdns = set()
        for _ in range(cfg.customers):
            while True:
                nine = make_msisdn_9digit(rng)
                msisdn = to_mtn_phone(nine)
                if msisdn not in used_msisdns:
                    used_msisdns.add(msisdn)
                    break
            city = rng.choice(all_cities_en if rng.random() < 0.95 else all_cities_en_with_unmapped[-3:])
            name = english_name(rng)
            registered = random_date(rng, period_start, today)
            client_rows.append((name, msisdn, city, registered))

        cur.executemany(
            "INSERT INTO clients (client_name, msisdn, city_en, registered_at) VALUES (%s, %s, %s, %s)",
            client_rows,
        )
        cur.execute("SELECT client_id FROM clients")
        client_ids = [r[0] for r in cur.fetchall()]

        heavy_ids = set(rng.sample(client_ids, k=max(1, len(client_ids) // 20)))

        # Transactions — NO total column, ETL must compute
        tx_rows = []
        for _ in range(cfg.orders):
            cid = rng.choice(client_ids)
            if rng.random() < 0.30:
                cid = rng.choice(list(heavy_ids))
            iid, price = rng.choice(items)
            qty = max(1, min(5, int(rng.gauss(1.2, 0.6))))
            tx_date = random_date(rng, period_start, today)
            tx_time = random_time(rng)
            tx_rows.append((cid, iid, qty, price, tx_date, tx_time))

        cur.executemany(
            "INSERT INTO transactions (client_id, item_id, qty, price_at_tx, tx_date, tx_time)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            tx_rows,
        )

    conn.commit()
    conn.close()
    print(f"[mtn] seeded: {len(client_rows)} clients, {len(item_rows)} items, {len(tx_rows)} transactions")


# ---- CLI ---------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--operator", choices=["syriatel", "mtn", "both"], default="both")
    p.add_argument("--customers", type=int, default=1000)
    p.add_argument("--products", type=int, default=15, help="(advisory — full catalog always loaded)")
    p.add_argument("--orders", type=int, default=10000)
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--reset", action="store_true", help="TRUNCATE before seeding")
    args = p.parse_args()

    cfg = SeedConfig(
        operator=args.operator,
        customers=args.customers,
        products=args.products,
        orders=args.orders,
        days=args.days,
        seed=args.seed,
        reset=args.reset,
    )

    rng = random.Random(cfg.seed)
    print(f"Seed config: {cfg}")

    if cfg.operator in ("syriatel", "both"):
        seed_syriatel(cfg, rng)
    if cfg.operator in ("mtn", "both"):
        # Reuse same RNG so the two OLTPs share population structure but diverge in storage
        seed_mtn(cfg, rng)

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
