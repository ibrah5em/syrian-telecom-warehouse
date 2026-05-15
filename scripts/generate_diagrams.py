"""Generate PNG diagrams for the README.

Outputs three files into docs/diagrams/:
- architecture.png   — three-tier system overview
- star_schema.png    — DW fact + dimensions and their FKs
- etl_pipeline.png   — six-stage ETL flow
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

SYRIATEL = "#D32F2F"   # red — Syriatel brand-adjacent
MTN      = "#FBC02D"   # yellow — MTN brand-adjacent
ETL      = "#1976D2"   # blue
DW       = "#388E3C"   # green
CONSUMER = "#7B1FA2"   # purple
LIGHT    = "#FAFAFA"
EDGE     = "#212121"


def box(ax, xy, w, h, title, lines=None, fill=LIGHT, edge=EDGE,
        title_color=EDGE, fontsize=10):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.04,rounding_size=0.12",
        linewidth=1.8, edgecolor=edge, facecolor=fill,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h - 0.32, title,
            ha="center", va="top", fontsize=fontsize + 1,
            fontweight="bold", color=title_color)
    if lines:
        for i, line in enumerate(lines):
            ax.text(x + w / 2, y + h - 0.7 - 0.32 * i, line,
                    ha="center", va="top", fontsize=fontsize - 1,
                    color="#424242")


def arrow(ax, src, dst, color=EDGE, lw=1.6, style="-|>"):
    a = FancyArrowPatch(src, dst, arrowstyle=style, mutation_scale=18,
                        linewidth=lw, color=color)
    ax.add_patch(a)


def make_architecture():
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 9)
    ax.set_axis_off()

    # Tier 1 — OLTP sources
    box(ax, (0.6, 6.8), 4.6, 1.9, "Syriatel OLTP",
        ["Postgres :5433  ·  Arabic-tilted",
         "SERIAL PK · INTEGER price",
         "TIMESTAMP · stored total"],
        fill="#FFEBEE", edge=SYRIATEL, title_color=SYRIATEL)

    box(ax, (6.8, 6.8), 4.6, 1.9, "MTN Syria OLTP",
        ["Postgres :5434  ·  English-tilted",
         "UUID PK · NUMERIC(12,2) price",
         "DATE + TIME · computed total"],
        fill="#FFF8E1", edge=MTN, title_color="#F57F17")

    # Tier 2 — ETL
    box(ax, (3.5, 3.9), 5, 1.9, "ETL Pipeline  (Python · pandas · psycopg)",
        ["Extract  →  Transform  →  Load",
         "Resolves all 9 divergences",
         "Idempotent · audited · quarantined"],
        fill="#E3F2FD", edge=ETL, title_color=ETL)

    # Tier 3 — DW
    box(ax, (3.5, 1.4), 5, 1.5, "Unified Data Warehouse",
        ["Postgres :5435  ·  Star schema",
         "fact_sales + 4 dims"],
        fill="#E8F5E9", edge=DW, title_color=DW)

    # Consumers
    box(ax, (0.4, 0.0), 3.4, 0.9, "6 SQL Analyses",
        fill="#F3E5F5", edge=CONSUMER, title_color=CONSUMER, fontsize=9)
    box(ax, (4.3, 0.0), 3.4, 0.9, "Metabase Dashboard",
        fill="#F3E5F5", edge=CONSUMER, title_color=CONSUMER, fontsize=9)
    box(ax, (8.2, 0.0), 3.4, 0.9, "Data Mining (RFM + Forecast)",
        fill="#F3E5F5", edge=CONSUMER, title_color=CONSUMER, fontsize=9)

    # Arrows
    arrow(ax, (2.9, 6.8), (5.0, 5.8), color=SYRIATEL)
    arrow(ax, (9.1, 6.8), (7.0, 5.8), color="#F57F17")
    arrow(ax, (6.0, 3.9), (6.0, 2.9), color=ETL)
    arrow(ax, (5.0, 1.4), (2.1, 0.9), color=DW)
    arrow(ax, (6.0, 1.4), (6.0, 0.9), color=DW)
    arrow(ax, (7.0, 1.4), (9.9, 0.9), color=DW)

    plt.title("Telecom DW — Three-Tier Architecture",
              fontsize=14, fontweight="bold", pad=8)
    plt.tight_layout()
    plt.savefig(OUT / "architecture.png", dpi=160, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    print("wrote", OUT / "architecture.png")


def make_star_schema():
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 9)
    ax.set_axis_off()

    # Center fact_sales
    fact_xy, fact_w, fact_h = (4.0, 3.4), 4.0, 2.4
    box(ax, fact_xy, fact_w, fact_h, "fact_sales",
        ["sale_sk  (PK)",
         "date_sk  (FK)",
         "customer_sk  (FK)",
         "product_sk  (FK)",
         "company_sk  (FK)",
         "quantity · unit_price_syp",
         "total_amount_syp",
         "etl_batch_id · etl_loaded_at"],
        fill="#FFFDE7", edge="#F57F17", title_color="#E65100",
        fontsize=10)

    # Dimensions — four corners
    dims = [
        # (name, xy, lines)
        ("dim_date",
         (0.4, 6.5),
         ["date_sk  (PK, YYYYMMDD)",
          "full_date · year · quarter",
          "month · day · day_of_week",
          "is_weekend (Fri/Sat)"]),
        ("dim_customer",
         (7.8, 6.5),
         ["customer_sk  (PK)",
          "source_system · source_nk",
          "full_name · phone_e164",
          "city · signup_date"]),
        ("dim_product",
         (0.4, 0.4),
         ["product_sk  (PK)",
          "source_system · source_nk",
          "product_name · category",
          "unit_price"]),
        ("dim_company",
         (7.8, 0.4),
         ["company_sk  (PK)",
          "company_code  (SYRIATEL/MTN)",
          "company_name_ar",
          "company_name_en"]),
    ]
    fx, fy = fact_xy
    fw, fh = fact_w, fact_h
    fact_anchors = {
        "dim_date":     (fx,      fy + fh),
        "dim_customer": (fx + fw, fy + fh),
        "dim_product":  (fx,      fy),
        "dim_company":  (fx + fw, fy),
    }
    dim_corners = {
        "dim_date":     lambda x, y, w, h: (x + w, y),
        "dim_customer": lambda x, y, w, h: (x,     y),
        "dim_product":  lambda x, y, w, h: (x + w, y + h),
        "dim_company":  lambda x, y, w, h: (x,     y + h),
    }
    for name, xy, lines in dims:
        w, h = 3.8, 2.0
        box(ax, xy, w, h, name, lines,
            fill="#E8F5E9", edge=DW, title_color=DW, fontsize=10)
        src = dim_corners[name](xy[0], xy[1], w, h)
        dst = fact_anchors[name]
        arrow(ax, src, dst, color="#757575", lw=1.6, style="-|>")

    plt.title("Unified Data Warehouse — Star Schema",
              fontsize=14, fontweight="bold", pad=8)
    plt.tight_layout()
    plt.savefig(OUT / "star_schema.png", dpi=160, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    print("wrote", OUT / "star_schema.png")


def make_etl_pipeline():
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6.5)
    ax.set_axis_off()

    stages = [
        ("Extract",
         ["per-operator SQL",
          "respects --since"],
         "#E3F2FD", ETL),
        ("Transform\nEntities",
         ["phone normalize",
          "city map",
          "category lift"],
         "#E3F2FD", ETL),
        ("Load\nDimensions",
         ["UPSERT dim_*",
          "return NK→SK"],
         "#E8F5E9", DW),
        ("Transform\nSales",
         ["compute MTN total",
          "validate Syriatel",
          "resolve SKs"],
         "#E3F2FD", ETL),
        ("Load\nFacts",
         ["ON CONFLICT",
          "DO NOTHING",
          "(idempotent)"],
         "#E8F5E9", DW),
        ("Audit",
         ["close etl_runs",
          "quarantine bad",
          "→ etl_errors"],
         "#FFF8E1", "#F57F17"),
    ]

    n = len(stages)
    box_w, box_h = 1.95, 2.2
    gap = (14 - n * box_w) / (n + 1)
    y = 2.3

    centers = []
    for i, (title, lines, fill, edge) in enumerate(stages):
        x = gap + i * (box_w + gap)
        box(ax, (x, y), box_w, box_h, title, lines,
            fill=fill, edge=edge, title_color=edge, fontsize=9)
        centers.append((x + box_w, y + box_h / 2,
                        x + box_w + gap, y + box_h / 2))

    # arrows between consecutive boxes
    for (x1, y1, x2, y2) in centers[:-1]:
        arrow(ax, (x1, y1), (x2, y2), color=EDGE, lw=1.6)

    # Side annotations
    ax.text(7, 5.5, "Six-stage ETL — every batch carries a UUID etl_batch_id",
            ha="center", va="center", fontsize=11, style="italic",
            color="#424242")
    ax.text(7, 0.7,
            "Modes:   python -m etl   |   --since YYYY-MM-DD   |   --full",
            ha="center", va="center", fontsize=10,
            color=ETL, fontweight="bold")

    plt.title("ETL Pipeline — Stages and Modes",
              fontsize=14, fontweight="bold", pad=8)
    plt.tight_layout()
    plt.savefig(OUT / "etl_pipeline.png", dpi=160, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    print("wrote", OUT / "etl_pipeline.png")


if __name__ == "__main__":
    make_architecture()
    make_star_schema()
    make_etl_pipeline()
