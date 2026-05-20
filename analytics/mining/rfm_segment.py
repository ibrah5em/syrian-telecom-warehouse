"""
RFM customer segmentation for the telecom-dw project.

Run from project root:
    python -m analytics.mining.rfm_segment

Reads raw RFM values from the DW, scores each customer on a 1–5 quintile
scale per dimension, assigns a named segment, and writes:
    analytics/mining/output/rfm_segments.csv
"""

import logging
import os
import pathlib
import sys

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SQL_FILE = pathlib.Path(__file__).parent / "rfm.sql"
OUTPUT_DIR = pathlib.Path(__file__).parent / "output"
OUTPUT_CSV = OUTPUT_DIR / "rfm_segments.csv"

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------
def get_conn():
    return psycopg.connect(
        host=os.environ["DW_HOST"],
        port=int(os.environ.get("DW_PORT", 5435)),
        user=os.environ["DW_USER"],
        password=os.environ["DW_PASSWORD"],
        dbname=os.environ["DW_DB"],
    )


# ---------------------------------------------------------------------------
# Segment labeling  (order matters — first match wins)
# ---------------------------------------------------------------------------
SEGMENT_RULES = [
    ("Champions",         lambda r: (r["r_score"] >= 4) & (r["f_score"] >= 4) & (r["m_score"] >= 4)),
    ("Loyal",             lambda r: (r["r_score"] >= 3) & (r["f_score"] >= 3)),
    ("At Risk",           lambda r: (r["r_score"] <= 2) & (r["f_score"] >= 3)),
    ("New",               lambda r: (r["r_score"] >= 4) & (r["f_score"] == 1)),
    ("Lost",              lambda r: (r["r_score"] == 1) & (r["f_score"] <= 2)),
    ("Other",             lambda r: pd.Series([True] * len(r), index=r.index)),
]


def assign_segment(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["segment"] = "Other"
    # Apply rules in reverse so higher-priority rules overwrite lower ones
    for name, rule in reversed(SEGMENT_RULES):
        mask = rule(df)
        df.loc[mask, "segment"] = name
    return df


# ---------------------------------------------------------------------------
# Scoring: quintile 1–5 using rank to break ties deterministically
# ---------------------------------------------------------------------------
def score_rfm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Recency: fewer days = more recent = score 5
    df["r_score"] = pd.qcut(
        -df["recency_days"].rank(method="first"),
        5,
        labels=[1, 2, 3, 4, 5],
    ).astype(int)

    # Frequency: more orders = higher score
    df["f_score"] = pd.qcut(
        df["frequency"].rank(method="first"),
        5,
        labels=[1, 2, 3, 4, 5],
    ).astype(int)

    # Monetary: higher spend = higher score
    df["m_score"] = pd.qcut(
        df["monetary_syp"].rank(method="first"),
        5,
        labels=[1, 2, 3, 4, 5],
    ).astype(int)

    df["rfm_code"] = (
        df["r_score"].astype(str)
        + df["f_score"].astype(str)
        + df["m_score"].astype(str)
    )
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log.info("Starting RFM segmentation")

    # Load SQL
    if SQL_FILE.exists():
        sql = SQL_FILE.read_text()
        # Use raw RFM values only (the NTILE scores in SQL are informational;
        # we re-derive scores in Python using qcut+rank for tie-breaking)
        raw_sql = """
            WITH ref AS (
                SELECT MAX(d.full_date) AS as_of_date
                FROM fact_sales f
                JOIN dim_date d ON d.date_sk = f.date_sk
            ),
            rfm_raw AS (
                SELECT
                    f.customer_sk,
                    dc.full_name,
                    dc.city,
                    dc.source_system,
                    co.company_name_en                                   AS company,
                    co.company_code,
                    (ref.as_of_date - MAX(d.full_date))::integer         AS recency_days,
                    COUNT(f.sale_sk)                                     AS frequency,
                    SUM(f.total_amount_syp)                              AS monetary_syp
                FROM fact_sales f
                JOIN dim_date     d  ON d.date_sk     = f.date_sk
                JOIN dim_customer dc ON dc.customer_sk = f.customer_sk
                JOIN dim_company  co ON co.company_sk  = f.company_sk
                CROSS JOIN ref
                GROUP BY
                    f.customer_sk,
                    dc.full_name,
                    dc.city,
                    dc.source_system,
                    co.company_name_en,
                    co.company_code,
                    ref.as_of_date
            )
            SELECT * FROM rfm_raw ORDER BY customer_sk
        """
    else:
        log.warning("rfm.sql not found, using embedded query")
        raw_sql = """
            WITH ref AS (
                SELECT MAX(d.full_date) AS as_of_date
                FROM fact_sales f
                JOIN dim_date d ON d.date_sk = f.date_sk
            ),
            rfm_raw AS (
                SELECT
                    f.customer_sk,
                    dc.full_name,
                    dc.city,
                    dc.source_system,
                    co.company_name_en AS company,
                    co.company_code,
                    (ref.as_of_date - MAX(d.full_date))::integer AS recency_days,
                    COUNT(f.sale_sk) AS frequency,
                    SUM(f.total_amount_syp) AS monetary_syp
                FROM fact_sales f
                JOIN dim_date     d  ON d.date_sk     = f.date_sk
                JOIN dim_customer dc ON dc.customer_sk = f.customer_sk
                JOIN dim_company  co ON co.company_sk  = f.company_sk
                CROSS JOIN ref
                GROUP BY
                    f.customer_sk, dc.full_name, dc.city, dc.source_system,
                    co.company_name_en, co.company_code, ref.as_of_date
            )
            SELECT * FROM rfm_raw ORDER BY customer_sk
        """

    # Connect and extract — use native cursor so psycopg3 works without SQLAlchemy
    log.info("Connecting to DW at %s:%s", os.environ["DW_HOST"], os.environ.get("DW_PORT", 5435))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(raw_sql)
            rows = cur.fetchall()
            cols = [desc.name for desc in cur.description]
    df = pd.DataFrame(rows, columns=cols)

    log.info("Extracted %d customers from DW", len(df))

    if len(df) == 0:
        log.error("No data returned from DW — is fact_sales populated?")
        sys.exit(1)

    # Score
    df = score_rfm(df)
    log.info("RFM scores computed. r_score range: %d–%d", df["r_score"].min(), df["r_score"].max())

    # Segment
    df = assign_segment(df)

    # Output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cols_out = [
        "customer_sk", "full_name", "city", "source_system", "company",
        "company_code", "recency_days", "frequency", "monetary_syp",
        "r_score", "f_score", "m_score", "rfm_code", "segment",
    ]
    df[cols_out].to_csv(OUTPUT_CSV, index=False)
    log.info("Saved CSV to %s", OUTPUT_CSV)

    # Distribution report
    dist = df["segment"].value_counts()
    total = len(df)
    print("\n=== RFM Segment Distribution ===")
    print(f"{'Segment':<20} {'Count':>6}  {'%':>6}")
    print("-" * 36)
    for seg, count in dist.items():
        print(f"{seg:<20} {count:>6}  {count/total*100:>5.1f}%")
    print(f"{'TOTAL':<20} {total:>6}  100.0%")

    # Sanity check: no segment dominates > 80%
    max_pct = dist.max() / total * 100
    if max_pct > 80:
        log.warning(
            "Largest segment holds %.1f%% of customers — quintile cuts may be degenerate",
            max_pct,
        )
    else:
        log.info("Segment distribution looks healthy (max bucket: %.1f%%)", max_pct)

    return df


if __name__ == "__main__":
    main()
