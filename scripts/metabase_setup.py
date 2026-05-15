#!/usr/bin/env python3
"""
Automate Metabase initial setup for the Telecom DW project.

Steps:
  1. Complete initial setup wizard (create admin, attach DW database)
  2. Authenticate and obtain session token
  3. Create "Ministry KPIs" collection
  4. Create 6 native-SQL questions (one per analytics file)
  5. Create one dashboard containing all 6 questions
"""

import json
import pathlib
import re
import sys
import time

import requests

BASE = "http://localhost:3000"
ANALYTICS = pathlib.Path(__file__).parent.parent / "analytics"

ADMIN_EMAIL    = "admin@telecom-dw.local"
ADMIN_PASSWORD = "Telecom@2025!"
ADMIN_FIRST    = "Admin"
ADMIN_LAST     = "Telecom"

DB_NAME   = "Telecom DW"
DB_HOST   = "dw"
DB_PORT   = 5432
DB_DBNAME = "telecom_dw"
DB_USER   = "dw_reader"
DB_PASS   = "reader_pw"

QUESTIONS = [
    {
        "file": "01_total_sales_per_company.sql",
        "name": "1 — Total Sales per Company",
        "display": "bar",
        "description": "Revenue and order share per operator (Syriatel vs MTN Syria).",
        "viz_settings": {
            "graph.dimensions": ["company_name_en"],
            "graph.metrics": ["total_sales_syp"],
        },
    },
    {
        "file": "02_top_customers.sql",
        "name": "2 — Top 20 Customers",
        "display": "table",
        "description": "Highest-spending customers across both operators.",
        "viz_settings": {},
    },
    {
        "file": "03_sales_by_city.sql",
        "name": "3 — Sales by City",
        "display": "bar",
        "description": "Revenue by Syrian city, split by operator.",
        "viz_settings": {
            "graph.dimensions": ["city"],
            "graph.metrics": ["syriatel_syp", "mtn_syp"],
            "stackable.stack_type": "stacked",
        },
    },
    {
        "file": "04_monthly_sales.sql",
        "name": "4 — Monthly Sales Trend",
        "display": "line",
        "description": "Monthly revenue per operator with MoM % change.",
        "viz_settings": {
            "graph.dimensions": ["year", "month"],
            "graph.metrics": ["sales_syp"],
            "graph.series_labels": ["company_code"],
        },
    },
    {
        "file": "05_company_comparison.sql",
        "name": "5 — Company Comparison",
        "display": "table",
        "description": "Side-by-side KPI comparison: revenue, orders, customers, AOV.",
        "viz_settings": {},
    },
    {
        "file": "06_decision_indicators.sql",
        "name": "6 — Decision Indicators",
        "display": "table",
        "description": "Composite KPIs for the Ministry: growth, concentration, cities.",
        "viz_settings": {},
    },
]


def load_sql(filename: str) -> str:
    path = ANALYTICS / filename
    raw = path.read_text()
    # Strip leading comment block — Metabase shows the query name separately
    lines = raw.splitlines()
    body_lines = []
    in_header = True
    for line in lines:
        if in_header and re.match(r"^\s*--", line):
            continue
        in_header = False
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def wait_for_metabase(timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/api/health", timeout=5)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(3)
    sys.exit("Metabase did not become healthy in time")


def get_setup_state() -> tuple[str | None, bool]:
    """Return (setup_token, has_user_setup)."""
    r = requests.get(f"{BASE}/api/session/properties")
    r.raise_for_status()
    props = r.json()
    return props.get("setup-token"), props.get("has-user-setup", False)


def initial_setup(token: str) -> str:
    payload = {
        "token": token,
        "user": {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "first_name": ADMIN_FIRST,
            "last_name": ADMIN_LAST,
            "site_name": "Telecom DW",
        },
        "database": None,
        "prefs": {"site_name": "Telecom DW", "allow_tracking": False},
    }
    r = requests.post(f"{BASE}/api/setup", json=payload)
    if r.status_code not in (200, 201):
        sys.exit(f"Setup failed {r.status_code}: {r.text}")
    session_id = r.json().get("id")
    print(f"  Setup complete. Session: {session_id[:8]}...")
    return session_id


def add_database(session: str) -> int:
    payload = {
        "engine": "postgres",
        "name": DB_NAME,
        "details": {
            "host": DB_HOST,
            "port": DB_PORT,
            "dbname": DB_DBNAME,
            "user": DB_USER,
            "password": DB_PASS,
            "ssl": False,
            "tunnel-enabled": False,
        },
        "auto_run_queries": True,
        "is_full_sync": True,
        "schedules": {},
    }
    r = requests.post(f"{BASE}/api/database", headers=headers(session), json=payload)
    if r.status_code not in (200, 201):
        sys.exit(f"Add database failed {r.status_code}: {r.text}")
    db_id = r.json()["id"]
    print(f"  Added database '{DB_NAME}' (id={db_id})")
    return db_id


def authenticate() -> str:
    r = requests.post(
        f"{BASE}/api/session",
        json={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    r.raise_for_status()
    return r.json()["id"]


def headers(session: str) -> dict:
    return {"X-Metabase-Session": session, "Content-Type": "application/json"}


def get_database_id(session: str, name: str) -> int:
    r = requests.get(f"{BASE}/api/database", headers=headers(session))
    r.raise_for_status()
    for db in r.json().get("data", r.json()):
        if isinstance(db, dict) and db.get("name") == name:
            return db["id"]
    sys.exit(f"Database '{name}' not found in Metabase")


def create_collection(session: str, name: str, description: str) -> int:
    # Check if already exists
    r = requests.get(f"{BASE}/api/collection", headers=headers(session))
    r.raise_for_status()
    for col in r.json():
        if col.get("name") == name:
            print(f"  Collection '{name}' already exists (id={col['id']})")
            return col["id"]
    r = requests.post(
        f"{BASE}/api/collection",
        headers=headers(session),
        json={"name": name, "description": description, "color": "#509EE3"},
    )
    r.raise_for_status()
    col_id = r.json()["id"]
    print(f"  Created collection '{name}' (id={col_id})")
    return col_id


def create_question(session: str, db_id: int, collection_id: int, q: dict) -> int:
    # Idempotent: skip if a card with the same name exists in the collection
    r = requests.get(
        f"{BASE}/api/collection/{collection_id}/items?models=card",
        headers=headers(session),
    )
    if r.status_code == 200:
        for item in r.json().get("data", []):
            if item.get("name") == q["name"]:
                cid = item["id"]
                print(f"  Question '{q['name']}' already exists (card_id={cid})")
                return cid

    sql = load_sql(q["file"])
    payload = {
        "name": q["name"],
        "description": q["description"],
        "display": q["display"],
        "dataset_query": {
            "type": "native",
            "native": {"query": sql, "template-tags": {}},
            "database": db_id,
        },
        "visualization_settings": q["viz_settings"],
        "collection_id": collection_id,
    }
    r = requests.post(f"{BASE}/api/card", headers=headers(session), json=payload)
    if r.status_code not in (200, 201):
        sys.exit(f"Card creation failed for '{q['name']}': {r.status_code} {r.text}")
    card_id = r.json()["id"]
    print(f"  Created question '{q['name']}' (card_id={card_id})")
    return card_id


DASHBOARD_NAME = "Ministry KPIs — Telecom DW"


def create_dashboard(session: str, collection_id: int, card_ids: list[int]) -> int:
    # Idempotent: reuse existing dashboard if found
    r = requests.get(
        f"{BASE}/api/collection/{collection_id}/items?models=dashboard",
        headers=headers(session),
    )
    if r.status_code == 200:
        for item in r.json().get("data", []):
            if item.get("name") == DASHBOARD_NAME:
                dash_id = item["id"]
                print(f"  Dashboard already exists (id={dash_id})")
                return dash_id

    r = requests.post(
        f"{BASE}/api/dashboard",
        headers=headers(session),
        json={
            "name": DASHBOARD_NAME,
            "description": "Six analytical dashboards for the Syrian Ministry of Communications.",
            "collection_id": collection_id,
        },
    )
    r.raise_for_status()
    dash_id = r.json()["id"]
    print(f"  Created dashboard (id={dash_id})")

    # Layout: 2 columns × 3 rows, each card 12 units wide × 8 units tall
    COLS, CARD_W, CARD_H = 2, 12, 8
    cards_payload = []
    for i, card_id in enumerate(card_ids):
        col = (i % COLS) * CARD_W
        row = (i // COLS) * CARD_H
        cards_payload.append({
            "id": -(i + 1),
            "card_id": card_id,
            "row": row,
            "col": col,
            "size_x": CARD_W,
            "size_y": CARD_H,
        })

    r = requests.put(
        f"{BASE}/api/dashboard/{dash_id}/cards",
        headers=headers(session),
        json={"cards": cards_payload},
    )
    if r.status_code not in (200, 201):
        sys.exit(f"Adding cards to dashboard failed: {r.status_code} {r.text}")
    print(f"  Added {len(card_ids)} cards to dashboard")
    return dash_id


def enable_public_link(session: str, dash_id: int) -> str | None:
    # Enable public sharing in admin settings
    requests.put(
        f"{BASE}/api/setting/enable-public-sharing",
        headers=headers(session),
        json={"value": True},
    )
    r = requests.post(
        f"{BASE}/api/dashboard/{dash_id}/public_link",
        headers=headers(session),
    )
    if r.status_code in (200, 201):
        uuid = r.json().get("uuid")
        return f"{BASE}/public/dashboard/{uuid}"
    return None


def main():
    print("Waiting for Metabase to be healthy...")
    wait_for_metabase()

    print("Checking setup state...")
    token, has_user = get_setup_state()

    if not has_user and token:
        print(f"  Got setup token: {token[:8]}...")
        print("Running initial setup wizard...")
        initial_setup(token)
    else:
        print("  Admin already created, skipping setup wizard.")

    print("Authenticating...")
    session = authenticate()

    print("Adding / looking up database...")
    try:
        db_id = get_database_id(session, DB_NAME)
        print(f"  Database '{DB_NAME}' already registered (id={db_id})")
    except SystemExit:
        db_id = add_database(session)

    print("Creating collection...")
    col_id = create_collection(session, "Ministry KPIs", "Telecom DW analytical dashboards")

    print("Creating questions (native SQL)...")
    card_ids = []
    for q in QUESTIONS:
        cid = create_question(session, db_id, col_id, q)
        card_ids.append(cid)

    print("Creating dashboard...")
    dash_id = create_dashboard(session, col_id, card_ids)

    print("Enabling public link...")
    public_url = enable_public_link(session, dash_id)

    print()
    print("=" * 60)
    print("Metabase setup complete!")
    print(f"  Admin UI:    {BASE}")
    print(f"  Email:       {ADMIN_EMAIL}")
    print(f"  Password:    {ADMIN_PASSWORD}")
    print(f"  Dashboard:   {BASE}/dashboard/{dash_id}")
    if public_url:
        print(f"  Public URL:  {public_url}")
    print("=" * 60)

    # Write summary for the report
    out = {
        "dashboard_id": dash_id,
        "dashboard_url": f"{BASE}/dashboard/{dash_id}",
        "public_url": public_url,
        "admin_email": ADMIN_EMAIL,
        "collection_id": col_id,
        "card_ids": dict(zip([q["name"] for q in QUESTIONS], card_ids)),
    }
    out_path = pathlib.Path(__file__).parent.parent / "docs" / "metabase_setup.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"  Saved summary → {out_path}")


if __name__ == "__main__":
    main()
