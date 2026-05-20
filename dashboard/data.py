"""
data.py — All DB queries and data transformations for the Dash dashboard.
Loads once at startup; exposes a single load_all_data() function.
"""

import logging
import os
import pathlib
import warnings

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# analytics/mining/output/ relative to the project root (one level above dashboard/)
_PROJECT_ROOT  = pathlib.Path(__file__).resolve().parent.parent
_MINING_OUTPUT = _PROJECT_ROOT / "analytics" / "mining" / "output"

DATABASE_URL = os.getenv("DATABASE_URL") or (
    "postgresql://{user}:{pw}@{host}:{port}/{db}".format(
        user=os.getenv("DB_USER", "postgres"),
        pw=os.getenv("DB_PASS", "postgres"),
        host=os.getenv("DB_HOST", "telecom_dw"),
        port=os.getenv("DB_PORT", "5432"),
        db=os.getenv("DB_NAME", "telecom_dw"),
    )
)

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _conn():
    return psycopg2.connect(DATABASE_URL)


def _qdf(sql: str) -> pd.DataFrame:
    conn = _conn()
    try:
        return pd.read_sql(sql, conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------

_Q_COMPANY_TOTALS = """
WITH totals AS (
    SELECT
        co.company_code,
        co.company_name_en,
        SUM(f.total_amount_syp)  AS total_sales_syp,
        COUNT(*)                  AS order_count,
        COUNT(DISTINCT f.customer_sk) AS customer_count
    FROM dw.fact_sales AS f
    JOIN dw.dim_company AS co ON co.company_sk = f.company_sk
    GROUP BY co.company_code, co.company_name_en
)
SELECT
    company_code,
    company_name_en,
    total_sales_syp,
    order_count,
    customer_count,
    ROUND(100.0 * total_sales_syp / SUM(total_sales_syp) OVER (), 2) AS share_pct,
    ROUND(total_sales_syp::numeric / NULLIF(order_count, 0), 2)       AS avg_order_syp
FROM totals
ORDER BY total_sales_syp DESC
"""

_Q_TOP_CUSTOMERS = """
SELECT
    c.customer_sk,
    c.full_name,
    c.source_system,
    c.city,
    SUM(f.total_amount_syp)           AS total_spent_syp,
    COUNT(*)                           AS order_count,
    ROUND(AVG(f.total_amount_syp), 2) AS avg_order_syp,
    MIN(d.full_date)                   AS first_order_date,
    MAX(d.full_date)                   AS last_order_date
FROM dw.fact_sales AS f
JOIN dw.dim_customer AS c ON c.customer_sk = f.customer_sk
JOIN dw.dim_date     AS d ON d.date_sk    = f.date_sk
GROUP BY c.customer_sk, c.full_name, c.source_system, c.city
ORDER BY total_spent_syp DESC
LIMIT 20
"""

_Q_CITY_SALES = """
SELECT
    c.city,
    SUM(CASE WHEN co.company_code = 'SYRIATEL' THEN f.total_amount_syp ELSE 0 END) AS syriatel_syp,
    SUM(CASE WHEN co.company_code = 'MTN'      THEN f.total_amount_syp ELSE 0 END) AS mtn_syp,
    SUM(f.total_amount_syp)          AS total_syp,
    COUNT(DISTINCT c.customer_sk)    AS unique_customers
FROM dw.fact_sales   AS f
JOIN dw.dim_customer AS c  ON c.customer_sk = f.customer_sk
JOIN dw.dim_company  AS co ON co.company_sk = f.company_sk
GROUP BY c.city
ORDER BY total_syp DESC
"""

_Q_MONTHLY_SALES = """
SELECT
    d.year,
    d.month,
    co.company_code,
    SUM(f.total_amount_syp) AS sales_syp,
    COUNT(*)                 AS order_count
FROM dw.fact_sales AS f
JOIN dw.dim_date    AS d  ON d.date_sk    = f.date_sk
JOIN dw.dim_company AS co ON co.company_sk = f.company_sk
GROUP BY d.year, d.month, co.company_code
ORDER BY co.company_code, d.year, d.month
"""

_Q_COMPANY_COMPARISON = """
SELECT
    co.company_code,
    co.company_name_en,
    SUM(f.total_amount_syp)                AS total_revenue_syp,
    COUNT(*)                                AS order_count,
    COUNT(DISTINCT f.customer_sk)           AS customer_count,
    ROUND(AVG(f.total_amount_syp), 2)       AS avg_order_value_syp,
    COUNT(DISTINCT c.city)                  AS cities_served,
    COUNT(DISTINCT p.category)              AS categories_sold,
    ROUND(SUM(f.total_amount_syp)::numeric
          / NULLIF(COUNT(DISTINCT f.customer_sk), 0), 2) AS revenue_per_customer_syp
FROM dw.fact_sales   AS f
JOIN dw.dim_company  AS co ON co.company_sk  = f.company_sk
JOIN dw.dim_customer AS c  ON c.customer_sk  = f.customer_sk
JOIN dw.dim_product  AS p  ON p.product_sk   = f.product_sk
GROUP BY co.company_code, co.company_name_en
ORDER BY total_revenue_syp DESC
"""

_Q_KPI_INDICATORS = """
WITH per_customer AS (
    SELECT f.customer_sk, SUM(f.total_amount_syp) AS customer_total
    FROM dw.fact_sales AS f
    GROUP BY f.customer_sk
),
ranked AS (
    SELECT customer_total,
           NTILE(10) OVER (ORDER BY customer_total DESC) AS decile
    FROM per_customer
),
top_decile AS (
    SELECT SUM(customer_total) AS top_decile_revenue
    FROM ranked WHERE decile = 1
),
totals AS (
    SELECT SUM(customer_total) AS grand_total FROM per_customer
),
ref_date AS (
    SELECT MAX(d.full_date) AS as_of
    FROM dw.dim_date d
    JOIN dw.fact_sales f ON f.date_sk = d.date_sk
),
trend AS (
    SELECT
        SUM(CASE
            WHEN d.full_date > (SELECT as_of FROM ref_date) - INTERVAL '3 months'
            THEN f.total_amount_syp ELSE 0 END) AS last_3m,
        SUM(CASE
            WHEN d.full_date <= (SELECT as_of FROM ref_date) - INTERVAL '3 months'
             AND d.full_date >  (SELECT as_of FROM ref_date) - INTERVAL '6 months'
            THEN f.total_amount_syp ELSE 0 END) AS prior_3m
    FROM dw.fact_sales f
    JOIN dw.dim_date d ON d.date_sk = f.date_sk
)
SELECT
    ROUND(100.0 * td.top_decile_revenue / NULLIF(t.grand_total, 0), 2) AS top_10pct_share,
    (SELECT COUNT(DISTINCT city) FROM dw.dim_customer)                   AS cities_served,
    (SELECT COUNT(*)             FROM dw.dim_customer)                   AS total_customers,
    ROUND(100.0 * (tr.last_3m - tr.prior_3m) / NULLIF(tr.prior_3m, 0), 2) AS qoq_growth_pct,
    tr.last_3m   AS last_3m_revenue_syp,
    t.grand_total AS total_revenue_syp
FROM top_decile td, totals t, trend tr
"""

_Q_PRODUCTS = """
SELECT
    p.product_name_en                 AS name,
    p.category,
    ROUND(AVG(f.total_amount_syp), 0) AS avg_price_syp,
    COUNT(*)                           AS order_count
FROM dw.fact_sales  AS f
JOIN dw.dim_product AS p ON p.product_sk = f.product_sk
GROUP BY p.product_name_en, p.category
ORDER BY avg_price_syp DESC
"""

_Q_RFM_RAW = """
WITH ref AS (
    SELECT MAX(dt.full_date) AS as_of_date
    FROM dw.fact_sales f
    JOIN dw.dim_date dt ON dt.date_sk = f.date_sk
)
SELECT
    f.customer_sk,
    dc.full_name,
    dc.city,
    dc.source_system,
    co.company_name_en                              AS company,
    co.company_code,
    (ref.as_of_date - MAX(dt.full_date))::integer   AS recency_days,
    COUNT(f.sale_sk)                                AS frequency,
    SUM(f.total_amount_syp)                         AS monetary_syp
FROM dw.fact_sales f
JOIN dw.dim_date     dt ON dt.date_sk     = f.date_sk
JOIN dw.dim_customer dc ON dc.customer_sk = f.customer_sk
JOIN dw.dim_company  co ON co.company_sk  = f.company_sk
CROSS JOIN ref
GROUP BY
    f.customer_sk, dc.full_name, dc.city, dc.source_system,
    co.company_name_en, co.company_code, ref.as_of_date
ORDER BY f.customer_sk
"""

# ---------------------------------------------------------------------------
# RFM Scoring & Segmentation
# ---------------------------------------------------------------------------

SEGMENT_RULES = [
    ("Champions", lambda r: (r["r_score"] >= 4) & (r["f_score"] >= 4) & (r["m_score"] >= 4)),
    ("Loyal",     lambda r: (r["r_score"] >= 3) & (r["f_score"] >= 3)),
    ("At Risk",   lambda r: (r["r_score"] <= 2) & (r["f_score"] >= 3)),
    ("New",       lambda r: (r["r_score"] >= 4) & (r["f_score"] == 1)),
    ("Lost",      lambda r: (r["r_score"] == 1) & (r["f_score"] <= 2)),
    ("Other",     lambda r: pd.Series([True] * len(r), index=r.index)),
]

SEGMENT_META = {
    "Champions": {"ar": "أبطال",             "color": "#F59E0B"},
    "Loyal":     {"ar": "مخلصون",            "color": "#10B981"},
    "At Risk":   {"ar": "معرضون للخطر",       "color": "#EF4444"},
    "New":       {"ar": "جدد",               "color": "#06B6D4"},
    "Lost":      {"ar": "مفقودون",            "color": "#8B5CF6"},
    "Other":     {"ar": "أخرى",              "color": "#6B7280"},
}

CITY_ARABIC = {
    "Damascus":    "دمشق",
    "Aleppo":      "حلب",
    "Homs":        "حمص",
    "Hama":        "حماة",
    "Latakia":     "اللاذقية",
    "Tartus":      "طرطوس",
    "Deir ez-Zor": "دير الزور",
    "Raqqa":       "الرقة",
    "Al-Hasakah":  "الحسكة",
    "Daraa":       "درعا",
    "As-Suwayda":  "السويداء",
    "Quneitra":    "القنيطرة",
    "Idlib":       "إدلب",
    "Rif Dimashq": "ريف دمشق",
}

COMPANY_ARABIC = {
    "SYRIATEL": "سيرياتل",
    "MTN":      "إم تي إن سوريا",
}


def _score_rfm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["r_score"] = pd.qcut(
        -df["recency_days"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]
    ).astype(int)
    df["f_score"] = pd.qcut(
        df["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]
    ).astype(int)
    df["m_score"] = pd.qcut(
        df["monetary_syp"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]
    ).astype(int)
    return df


def _assign_segments(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["segment"] = "Other"
    for name, rule in reversed(SEGMENT_RULES):
        df.loc[rule(df), "segment"] = name
    return df


def _build_rfm_summary(rfm_df: pd.DataFrame) -> pd.DataFrame:
    dist = rfm_df["segment"].value_counts().reset_index()
    dist.columns = ["segment", "count"]
    total = dist["count"].sum()
    dist["pct"] = (dist["count"] / total * 100).round(1)
    dist["color"] = dist["segment"].map(lambda s: SEGMENT_META[s]["color"])
    dist["segment_ar"] = dist["segment"].map(lambda s: SEGMENT_META[s]["ar"])
    return dist


# ---------------------------------------------------------------------------
# Forecast (Holt-Winters)
# ---------------------------------------------------------------------------

def _compute_forecast(monthly_df: pd.DataFrame) -> dict:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
    except ImportError:
        log.warning("statsmodels not available; returning fallback forecast")
        return _fallback_forecast()

    results = {}
    for code in ["SYRIATEL", "MTN"]:
        sub = monthly_df[monthly_df["company_code"] == code].copy()
        sub["period"] = pd.to_datetime(
            sub["year"].astype(str) + "-" + sub["month"].astype(str).str.zfill(2) + "-01"
        )
        sub = sub.sort_values("period").set_index("period")["sales_syp"].astype(float)

        if len(sub) < 3:
            log.warning("Too few data points for %s forecast", code)
            continue

        # Drop last partial month
        if len(sub) > 1:
            sub = sub.iloc[:-1]

        model = ExponentialSmoothing(
            sub.values, trend="add", seasonal=None,
            initialization_method="estimated",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = model.fit(optimized=True)

        n_fc = 3
        fc_index = pd.date_range(
            sub.index[-1] + pd.DateOffset(months=1), periods=n_fc, freq="MS"
        )
        fitted_s = pd.Series(fit.fittedvalues, index=sub.index)
        forecast_s = pd.Series(fit.forecast(n_fc), index=fc_index)

        actual_v, fitted_v = sub.values, fitted_s.values
        rmse = float(np.sqrt(np.mean((actual_v - fitted_v) ** 2)))
        with np.errstate(divide="ignore", invalid="ignore"):
            ape = np.where(actual_v != 0, np.abs((actual_v - fitted_v) / actual_v), np.nan)
        mape = float(np.nanmean(ape) * 100)

        results[code] = {
            "actual": sub,
            "fitted": fitted_s,
            "forecast": forecast_s,
            "rmse": rmse,
            "mape": mape,
        }
    return results


def _fallback_forecast() -> dict:
    # Reference values from JSX mock data (in SYP, i.e. multiply M values × 1e6)
    fc_index = pd.to_datetime(["2026-05-01", "2026-06-01", "2026-07-01"])
    return {
        "SYRIATEL": {
            "actual": pd.Series(dtype=float),
            "fitted": pd.Series(dtype=float),
            "forecast": pd.Series([64.7e6, 66.2e6, 67.6e6], index=fc_index),
            "rmse": 7.38e6,
            "mape": 12.98,
        },
        "MTN": {
            "actual": pd.Series(dtype=float),
            "fitted": pd.Series(dtype=float),
            "forecast": pd.Series([64.6e6, 65.9e6, 67.3e6], index=fc_index),
            "rmse": 7.82e6,
            "mape": 12.91,
        },
    }


# ---------------------------------------------------------------------------
# CSV-based loaders (preferred over live DB computation)
# ---------------------------------------------------------------------------

def load_rfm_data() -> pd.DataFrame:
    """
    Read analytics/mining/output/rfm_segments.csv and return a segment-summary
    DataFrame with columns: segment, count, pct, color, segment_ar.

    Shape is identical to the DataFrame produced by _build_rfm_summary() so
    customers_tab() can consume either source without modification.
    """
    csv_path = _MINING_OUTPUT / "rfm_segments.csv"
    df = pd.read_csv(csv_path)
    # rfm_segments.csv has a 'segment' column for every customer row
    return _build_rfm_summary(df)


def load_forecast_data() -> dict:
    """
    Read analytics/mining/output/forecast-syriatel.csv and forecast-mtn.csv.

    Each file has columns: period (YYYY-MM), type (actual|fitted|forecast), sales_syp.
    Returns a dict keyed by company code with sub-keys matching _compute_forecast():
        actual   — pd.Series[float] indexed by month-start datetime (SYP)
        fitted   — pd.Series[float] indexed by month-start datetime (SYP)
        forecast — pd.Series[float] indexed by month-start datetime (SYP)
        rmse     — float (in-sample, SYP)
        mape     — float (in-sample, %)
    """
    _CODE_TO_FILE = {
        "SYRIATEL": "forecast-syriatel.csv",
        "MTN":      "forecast-mtn.csv",
    }
    result = {}
    for code, fname in _CODE_TO_FILE.items():
        df = pd.read_csv(_MINING_OUTPUT / fname)
        # "2025-05" → Timestamp("2025-05-01")
        df["period"] = pd.to_datetime(df["period"] + "-01")
        df = df.set_index("period")

        actual   = df.loc[df["type"] == "actual",   "sales_syp"].astype(float)
        fitted   = df.loc[df["type"] == "fitted",   "sales_syp"].astype(float)
        forecast = df.loc[df["type"] == "forecast", "sales_syp"].astype(float)

        # Recompute in-sample metrics from the pre-fitted values
        actual_v = actual.values
        fitted_v = fitted.values
        rmse = float(np.sqrt(np.mean((actual_v - fitted_v) ** 2)))
        with np.errstate(divide="ignore", invalid="ignore"):
            ape = np.where(actual_v != 0,
                           np.abs((actual_v - fitted_v) / actual_v),
                           np.nan)
        mape = float(np.nanmean(ape) * 100)

        result[code] = {
            "actual":   actual,
            "fitted":   fitted,
            "forecast": forecast,
            "rmse":     rmse,
            "mape":     mape,
        }
        log.debug(
            "Forecast CSV loaded for %s — %d actual, %d fitted, %d forecast rows; "
            "RMSE=%.2fM MAPE=%.1f%%",
            code, len(actual), len(fitted), len(forecast), rmse / 1e6, mape,
        )
    return result


# ---------------------------------------------------------------------------
# Monthly pivot helper (used by charts)
# ---------------------------------------------------------------------------

def build_monthly_wide(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot monthly long → wide; columns SYRIATEL / MTN in millions SYP."""
    pivot = monthly_df.pivot_table(
        index=["year", "month"],
        columns="company_code",
        values="sales_syp",
        aggfunc="sum",
    ).reset_index()
    pivot.columns.name = None
    pivot["period"] = pd.to_datetime(
        pivot["year"].astype(str) + "-" + pivot["month"].astype(str).str.zfill(2) + "-01"
    )
    pivot = pivot.sort_values("period").reset_index(drop=True)
    pivot["label"] = pivot["period"].dt.strftime("%b %y")
    for col in ["SYRIATEL", "MTN"]:
        if col in pivot.columns:
            pivot[col] = pivot[col] / 1e6
        else:
            pivot[col] = 0.0
    return pivot


# ---------------------------------------------------------------------------
# Main loader (called once at startup)
# ---------------------------------------------------------------------------

_cache: dict | None = None


def load_all_data() -> dict | None:
    global _cache
    if _cache is not None:
        return _cache

    log.info("Loading data from %s", DATABASE_URL)
    try:
        company_df     = _qdf(_Q_COMPANY_TOTALS)
        top_cust_df    = _qdf(_Q_TOP_CUSTOMERS)
        city_df        = _qdf(_Q_CITY_SALES)
        monthly_df     = _qdf(_Q_MONTHLY_SALES)
        comparison_df  = _qdf(_Q_COMPANY_COMPARISON)
        kpi_df         = _qdf(_Q_KPI_INDICATORS)
        products_df    = _qdf(_Q_PRODUCTS)
        rfm_raw_df     = _qdf(_Q_RFM_RAW)

        # Derived columns — city DataFrame
        city_df["syriatel_m"] = city_df["syriatel_syp"] / 1e6
        city_df["mtn_m"]      = city_df["mtn_syp"] / 1e6
        city_df["total_m"]    = city_df["total_syp"] / 1e6
        city_df["city_ar"]    = city_df["city"].map(lambda c: CITY_ARABIC.get(c, c))

        # Monthly wide pivot
        monthly_wide = build_monthly_wide(monthly_df)

        # RFM — DB scoring used as fallback; CSV output preferred
        rfm_df = _score_rfm(rfm_raw_df)
        rfm_df = _assign_segments(rfm_df)
        rfm_summary = _build_rfm_summary(rfm_df)
        try:
            rfm_summary = load_rfm_data()
            log.info("RFM summary sourced from CSV (%s)", _MINING_OUTPUT / "rfm_segments.csv")
        except Exception as exc:
            log.warning("CSV RFM unavailable (%s) — using DB-scored segmentation", exc)

        # Forecast — live Holt-Winters used as fallback; CSV output preferred
        forecast = _compute_forecast(monthly_df)
        try:
            forecast = load_forecast_data()
            log.info("Forecast sourced from CSV (%s)", _MINING_OUTPUT)
        except Exception as exc:
            log.warning("CSV forecast unavailable (%s) — using live Holt-Winters computation", exc)

        # KPI convenience values
        kpi_row = kpi_df.iloc[0]
        total_rev_syp = float(kpi_row["total_revenue_syp"])
        total_orders  = int(company_df["order_count"].sum())
        total_cust    = int(kpi_row["total_customers"])
        cities_served = int(kpi_row["cities_served"])
        avg_order     = float(total_rev_syp / total_orders) if total_orders else 0
        qoq_growth    = float(kpi_row["qoq_growth_pct"])
        top10_share   = float(kpi_row["top_10pct_share"])

        at_risk_count = int(rfm_summary.loc[rfm_summary["segment"] == "At Risk", "count"].sum()) if "At Risk" in rfm_summary["segment"].values else 0
        champ_loyal   = int(rfm_summary.loc[rfm_summary["segment"].isin(["Champions", "Loyal"]), "count"].sum())

        _cache = {
            "company":      company_df,
            "top_customers": top_cust_df,
            "city":         city_df,
            "monthly":      monthly_df,
            "monthly_wide": monthly_wide,
            "comparison":   comparison_df,
            "kpi_row":      kpi_row,
            "products":     products_df,
            "rfm":          rfm_df,
            "rfm_summary":  rfm_summary,
            "forecast":     forecast,
            # Scalar KPIs
            "total_rev_syp":  total_rev_syp,
            "total_orders":   total_orders,
            "total_customers": total_cust,
            "cities_served":  cities_served,
            "avg_order_syp":  avg_order,
            "qoq_growth":     qoq_growth,
            "top10_share":    top10_share,
            "at_risk_count":  at_risk_count,
            "champ_loyal_count": champ_loyal,
        }

        log.info(
            "Data loaded — %d company rows, %d city rows, %d monthly rows, %d customers",
            len(company_df), len(city_df), len(monthly_df), len(rfm_raw_df),
        )

    except Exception:
        log.exception("Failed to load warehouse data")
        _cache = None

    return _cache
