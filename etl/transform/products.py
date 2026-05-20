"""Transform product data from both operators into a unified dim_product shape.

Divergence resolved here:
  - Category case: Syriatel Title Case (Internet) → UPPER (INTERNET)
  - Product names: Syriatel Arabic → canonical English via product catalog lookup
  - Table naming: products / items → unified source_system + source_product_id
  - Price type: Syriatel INTEGER → NUMERIC (stored as Python float for pandas)
"""
from __future__ import annotations

from typing import NamedTuple

import pandas as pd

from etl.utils.logging import get_logger
from etl.utils.mappings import load_product_catalog

logger = get_logger(__name__)

_CAT_TITLE_TO_UPPER = {"Internet": "INTERNET", "Voice": "VOICE", "Bundle": "BUNDLE"}
_VALID_UPPER_CATS   = {"INTERNET", "VOICE", "BUNDLE"}

_DIM_COLS = [
    "source_system", "source_product_id",
    "product_name_en", "category", "unit_price_syp",
]


class ProductResult(NamedTuple):
    records: pd.DataFrame
    quarantine: list[dict]


def _build_catalog_lookups(catalog: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return (by_ar_name, by_en_name) lookup dicts over the shared product catalog."""
    by_ar: dict[str, dict] = {}
    by_en: dict[str, dict] = {}
    for row in catalog:
        by_ar[row["syriatel_name_ar"]] = row
        by_en[row["mtn_name_en"]]      = row
    return by_ar, by_en


def _transform_syriatel(df: pd.DataFrame, by_ar: dict) -> tuple[list[dict], list[dict]]:
    good: list[dict] = []
    bad: list[dict] = []
    for row in df.itertuples(index=False):
        try:
            cat = _CAT_TITLE_TO_UPPER.get(row.category)
            if cat is None:
                raise ValueError(f"unknown Syriatel category: {row.category!r}")
            entry = by_ar.get(row.product_name)
            en_name = entry["mtn_name_en"] if entry else row.product_name
            good.append({
                "source_system":    "SYRIATEL",
                "source_product_id": str(row.product_id),
                "product_name_en":  en_name,
                "category":         cat,
                "unit_price_syp":   float(row.unit_price),
            })
        except (ValueError, TypeError) as exc:
            bad.append({
                "source_system": "SYRIATEL",
                "source_table":  "products",
                "source_row":    dict(zip(df.columns, row)),
                "reason":        str(exc),
            })
    return good, bad


def _transform_mtn(df: pd.DataFrame, by_en: dict) -> tuple[list[dict], list[dict]]:
    good: list[dict] = []
    bad: list[dict] = []
    for row in df.itertuples(index=False):
        try:
            if row.item_type not in _VALID_UPPER_CATS:
                raise ValueError(f"unknown MTN item_type: {row.item_type!r}")
            entry = by_en.get(row.item_name)
            en_name = entry["mtn_name_en"] if entry else row.item_name
            good.append({
                "source_system":    "MTN",
                "source_product_id": str(row.item_id),
                "product_name_en":  en_name,
                "category":         row.item_type,
                "unit_price_syp":   float(row.price_syp),
            })
        except (ValueError, TypeError) as exc:
            bad.append({
                "source_system": "MTN",
                "source_table":  "items",
                "source_row":    dict(zip(df.columns, row)),
                "reason":        str(exc),
            })
    return good, bad


def transform(syr_data: dict, mtn_data: dict) -> ProductResult:
    catalog = load_product_catalog()
    by_ar, by_en = _build_catalog_lookups(catalog)

    syr_good, syr_bad = _transform_syriatel(syr_data["products"], by_ar)
    mtn_good, mtn_bad = _transform_mtn(mtn_data["items"], by_en)

    all_good = syr_good + mtn_good
    all_bad  = syr_bad  + mtn_bad

    logger.info(
        "transform.products: %d ok, %d quarantined",
        len(all_good), len(all_bad),
    )

    return ProductResult(
        records=pd.DataFrame(all_good, columns=_DIM_COLS) if all_good else pd.DataFrame(columns=_DIM_COLS),
        quarantine=all_bad,
    )
