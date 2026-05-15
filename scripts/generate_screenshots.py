"""Generate analytics chart PNGs for the Arabic report."""

import os
import pathlib
import psycopg
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).parents[1] / ".env")

DSN = (
    f"host={os.getenv('DW_HOST', 'localhost')} "
    f"port={os.getenv('DW_PORT', '5435')} "
    f"dbname={os.getenv('DW_DB', 'telecom_dw')} "
    f"user={os.getenv('DW_USER', 'dw')} "
    f"password={os.getenv('DW_PASSWORD', 'dw')}"
)

OUT = pathlib.Path(__file__).parents[1] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

# ── palette ──────────────────────────────────────────────────────────────────
SYRIATEL_COLOR = "#1A73E8"
MTN_COLOR = "#F4A300"
COLORS = [SYRIATEL_COLOR, MTN_COLOR]

plt.rcParams.update({
    "figure.facecolor": "#FAFAFA",
    "axes.facecolor":   "#FAFAFA",
    "axes.spines.top":  False,
    "axes.spines.right": False,
    "axes.grid":        True,
    "grid.color":       "#E0E0E0",
    "grid.linewidth":   0.6,
    "font.family":      "DejaVu Sans",
    "font.size":        11,
    "axes.titlesize":   14,
    "axes.titleweight": "bold",
    "axes.labelsize":   11,
})

def syp(val):
    """Format large SYP values as '702M SYP'."""
    if val >= 1_000_000:
        return f"{val/1_000_000:.0f}M"
    if val >= 1_000:
        return f"{val/1_000:.0f}K"
    return str(int(val))


def save(fig, name):
    path = OUT / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {path}")


with psycopg.connect(DSN) as conn:

    # ── Q1: Total Sales per Company ──────────────────────────────────────────
    df1 = pd.read_sql("""
        WITH t AS (
            SELECT co.company_name_en,
                   SUM(f.total_amount_syp) AS total_sales_syp,
                   COUNT(*)                AS order_count
            FROM dw.fact_sales f
            JOIN dw.dim_company co ON co.company_sk = f.company_sk
            GROUP BY co.company_name_en
        )
        SELECT *, ROUND(100.0*total_sales_syp/SUM(total_sales_syp) OVER(),2) AS share_pct
        FROM t ORDER BY total_sales_syp DESC
    """, conn)

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    fig.suptitle("Q1 — Total Sales per Operator", fontsize=15, fontweight="bold", y=1.01)

    bars = axes[0].bar(df1["company_name_en"], df1["total_sales_syp"] / 1e6,
                       color=COLORS, edgecolor="white", width=0.5)
    axes[0].set_ylabel("Revenue (Million SYP)")
    axes[0].set_title("Total Revenue")
    for bar, val in zip(bars, df1["total_sales_syp"]):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                     f"{syp(val)} SYP", ha="center", va="bottom", fontsize=10, fontweight="bold")

    wedges, texts, autotexts = axes[1].pie(
        df1["share_pct"], labels=df1["company_name_en"],
        colors=COLORS, autopct="%1.1f%%", startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2})
    for at in autotexts:
        at.set_fontsize(12)
        at.set_fontweight("bold")
    axes[1].set_title("Market Share")

    plt.tight_layout()
    save(fig, "analytics-01-total-sales-per-company.png")

    # ── Q2: Top 20 Customers ─────────────────────────────────────────────────
    df2 = pd.read_sql("""
        SELECT c.full_name, c.source_system,
               SUM(f.total_amount_syp) AS total_spent_syp,
               COUNT(*)                AS order_count
        FROM dw.fact_sales f
        JOIN dw.dim_customer c ON c.customer_sk = f.customer_sk
        GROUP BY c.full_name, c.source_system
        ORDER BY total_spent_syp DESC
        LIMIT 20
    """, conn)

    df2["label"] = df2["full_name"].str[:22]
    colors_q2 = [SYRIATEL_COLOR if s == "SYRIATEL" else MTN_COLOR for s in df2["source_system"]]

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(df2["label"][::-1], df2["total_spent_syp"][::-1] / 1e6,
                   color=colors_q2[::-1], edgecolor="white")
    ax.set_xlabel("Total Spend (Million SYP)")
    ax.set_title("Q2 — Top 20 Customers by Total Spend")
    for bar, val in zip(bars, df2["total_spent_syp"][::-1]):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                f"{syp(val)}", va="center", fontsize=9)

    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=SYRIATEL_COLOR, label="Syriatel"),
                        Patch(facecolor=MTN_COLOR,      label="MTN Syria")],
              loc="lower right")
    plt.tight_layout()
    save(fig, "analytics-02-top-customers.png")

    # ── Q3: Sales by City ────────────────────────────────────────────────────
    df3 = pd.read_sql("""
        SELECT c.city,
               SUM(CASE WHEN co.company_code='SYRIATEL' THEN f.total_amount_syp ELSE 0 END) AS syriatel_syp,
               SUM(CASE WHEN co.company_code='MTN'      THEN f.total_amount_syp ELSE 0 END) AS mtn_syp,
               SUM(f.total_amount_syp) AS total_syp
        FROM dw.fact_sales f
        JOIN dw.dim_customer c  ON c.customer_sk = f.customer_sk
        JOIN dw.dim_company  co ON co.company_sk = f.company_sk
        GROUP BY c.city
        ORDER BY total_syp DESC
    """, conn)

    fig, ax = plt.subplots(figsize=(13, 6))
    x = range(len(df3))
    width = 0.38
    b1 = ax.bar([i - width/2 for i in x], df3["syriatel_syp"] / 1e6,
                width=width, color=SYRIATEL_COLOR, label="Syriatel", edgecolor="white")
    b2 = ax.bar([i + width/2 for i in x], df3["mtn_syp"] / 1e6,
                width=width, color=MTN_COLOR, label="MTN Syria", edgecolor="white")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df3["city"], rotation=40, ha="right", fontsize=9)
    ax.set_ylabel("Revenue (Million SYP)")
    ax.set_title("Q3 — Revenue by City (Operator Breakdown)")
    ax.legend()
    plt.tight_layout()
    save(fig, "analytics-03-sales-by-city.png")

    # ── Q4: Monthly Sales ────────────────────────────────────────────────────
    df4 = pd.read_sql("""
        SELECT d.year, d.month, co.company_code,
               SUM(f.total_amount_syp) AS sales_syp
        FROM dw.fact_sales f
        JOIN dw.dim_date    d  ON d.date_sk    = f.date_sk
        JOIN dw.dim_company co ON co.company_sk = f.company_sk
        GROUP BY d.year, d.month, co.company_code
        ORDER BY d.year, d.month, co.company_code
    """, conn)
    df4["period"] = pd.to_datetime(
        df4["year"].astype(str) + "-" + df4["month"].astype(str).str.zfill(2) + "-01"
    )

    fig, ax = plt.subplots(figsize=(13, 5))
    for company, color in zip(["SYRIATEL", "MTN"], COLORS):
        sub = df4[df4["company_code"] == company].sort_values("period")
        ax.plot(sub["period"], sub["sales_syp"] / 1e6,
                marker="o", markersize=5, linewidth=2,
                color=color, label=company.title() if company == "SYRIATEL" else "MTN Syria")
        ax.fill_between(sub["period"], sub["sales_syp"] / 1e6, alpha=0.08, color=color)

    ax.set_ylabel("Revenue (Million SYP)")
    ax.set_title("Q4 — Monthly Sales Trend per Operator")
    ax.legend()
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %Y"))
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    save(fig, "analytics-04-monthly-sales.png")

    # ── Q5: Company Comparison ───────────────────────────────────────────────
    df5 = pd.read_sql("""
        SELECT co.company_name_en,
               SUM(f.total_amount_syp)                                     AS total_revenue_syp,
               COUNT(*)                                                     AS order_count,
               COUNT(DISTINCT f.customer_sk)                                AS customer_count,
               ROUND(AVG(f.total_amount_syp), 0)                           AS avg_order_value_syp,
               COUNT(DISTINCT c.city)                                       AS cities_served,
               ROUND(SUM(f.total_amount_syp)::numeric
                     / NULLIF(COUNT(DISTINCT f.customer_sk), 0), 0)        AS revenue_per_customer_syp
        FROM dw.fact_sales f
        JOIN dw.dim_company  co ON co.company_sk = f.company_sk
        JOIN dw.dim_customer c  ON c.customer_sk = f.customer_sk
        JOIN dw.dim_product  p  ON p.product_sk  = f.product_sk
        GROUP BY co.company_name_en
        ORDER BY total_revenue_syp DESC
    """, conn)

    metrics = ["total_revenue_syp", "order_count", "customer_count",
               "avg_order_value_syp", "cities_served", "revenue_per_customer_syp"]
    labels  = ["Total Revenue\n(SYP)", "Orders", "Customers",
               "Avg Order\n(SYP)", "Cities\nServed", "Revenue /\nCustomer (SYP)"]

    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    fig.suptitle("Q5 — Side-by-Side Operator Comparison", fontsize=15, fontweight="bold")

    for ax, metric, label in zip(axes.flat, metrics, labels):
        vals = df5[metric].astype(float).tolist()
        bars = ax.bar(df5["company_name_en"], vals, color=COLORS, edgecolor="white", width=0.5)
        ax.set_title(label, fontsize=10)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(df5["company_name_en"], fontsize=9)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(
            lambda v, _: f"{v/1e6:.0f}M" if v >= 1e6 else f"{v:,.0f}"))
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.02,
                    f"{val/1e6:.1f}M" if val >= 1e6 else f"{val:,.0f}",
                    ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.tight_layout()
    save(fig, "analytics-05-company-comparison.png")

    # ── Q6: Decision Indicators ──────────────────────────────────────────────
    df6 = pd.read_sql("""
        WITH per_customer AS (
            SELECT customer_sk, SUM(total_amount_syp) AS ct FROM dw.fact_sales GROUP BY customer_sk
        ),
        ranked AS (SELECT ct, NTILE(10) OVER (ORDER BY ct DESC) AS decile FROM per_customer),
        ref_date AS (SELECT MAX(d.full_date) AS as_of FROM dw.dim_date d JOIN dw.fact_sales f ON f.date_sk=d.date_sk),
        trend AS (
            SELECT
                SUM(CASE WHEN d.full_date > (SELECT as_of FROM ref_date) - INTERVAL '3 months'
                         THEN f.total_amount_syp ELSE 0 END) AS last_3m,
                SUM(CASE WHEN d.full_date <= (SELECT as_of FROM ref_date) - INTERVAL '3 months'
                          AND d.full_date > (SELECT as_of FROM ref_date) - INTERVAL '6 months'
                         THEN f.total_amount_syp ELSE 0 END) AS prior_3m
            FROM dw.fact_sales f JOIN dw.dim_date d ON d.date_sk=f.date_sk
        )
        SELECT
            ROUND(100.0*(SELECT SUM(ct) FROM ranked WHERE decile=1)
                  / NULLIF((SELECT SUM(ct) FROM per_customer),0),2)    AS top10_share_pct,
            (SELECT COUNT(DISTINCT city) FROM dw.dim_customer)         AS cities_served,
            (SELECT COUNT(*) FROM dw.dim_customer)                     AS total_customers,
            ROUND(100.0*(last_3m-prior_3m)/NULLIF(prior_3m,0),2)     AS qoq_growth_pct,
            last_3m                                                    AS last_3m_syp,
            prior_3m                                                   AS prior_3m_syp,
            (SELECT SUM(total_amount_syp) FROM dw.fact_sales)         AS grand_total_syp
        FROM trend
    """, conn)

    kpis_list = [
        ("Grand Total Revenue",          f"{df6['grand_total_syp'].iloc[0]/1e9:.2f}B SYP", "#1A73E8"),
        ("QoQ Growth",                   f"{df6['qoq_growth_pct'].iloc[0]:+.1f}%",         "#E84040"),
        ("Top 10% Customers\nRevenue Share", f"{df6['top10_share_pct'].iloc[0]:.1f}%",      "#F4A300"),
        ("Cities Served",                f"{int(df6['cities_served'].iloc[0])}",            "#34A853"),
        ("Total Customers",              f"{int(df6['total_customers'].iloc[0]):,}",         "#9C27B0"),
        ("Last 3M Revenue",              f"{syp(float(df6['last_3m_syp'].iloc[0]))} SYP",   "#00ACC1"),
    ]

    from matplotlib.patches import FancyBboxPatch
    fig, axes = plt.subplots(2, 3, figsize=(13, 6))
    fig.patch.set_facecolor("#FAFAFA")
    fig.suptitle("Q6 — Ministry Decision Indicators (KPIs)", fontsize=15, fontweight="bold")

    for ax, (label, val, color) in zip(axes.flat, kpis_list):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        rect = FancyBboxPatch(
            (0.0, 0.0), 1.0, 1.0,
            boxstyle="round,pad=0.0",
            facecolor=color, edgecolor="white", linewidth=3,
            transform=ax.transAxes, zorder=0, clip_on=False,
        )
        ax.add_patch(rect)
        ax.text(0.5, 0.60, val, ha="center", va="center",
                fontsize=24, fontweight="bold", color="white",
                transform=ax.transAxes, zorder=1)
        ax.text(0.5, 0.22, label, ha="center", va="center",
                fontsize=10, color="white", alpha=0.92,
                transform=ax.transAxes, zorder=1, linespacing=1.4)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    save(fig, "analytics-06-decision-indicators.png")

print("\nDone — 6 PNGs written to docs/screenshots/")
