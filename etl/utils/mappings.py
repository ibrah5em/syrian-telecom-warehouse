"""
Reference-data mappers. Loaded once per pipeline run.

City mapping: data/syrian_cities.csv  →  Arabic ↔ English
Product mapping: data/product_catalog.csv  →  offering_id ↔ syriatel/mtn names

Missing mappings cause the row to be quarantined (NOT silently guessed).
"""
from __future__ import annotations

import csv
from pathlib import Path

_DATA_DIR = Path(__file__).parents[2] / "data"


def load_city_map_ar_to_en() -> dict[str, str]:
    """Return Arabic → English city name mapping from data/syrian_cities.csv."""
    out: dict[str, str] = {}
    path = _DATA_DIR / "syrian_cities.csv"
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["ar"].strip()] = row["en"].strip()
    return out


def load_city_map_en_to_canonical() -> dict[str, str]:
    """English city name → canonical English (handles e.g. 'Aleppo' ↔ 'Aleppo')."""
    out: dict[str, str] = {}
    path = _DATA_DIR / "syrian_cities.csv"
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            en = row["en"].strip()
            out[en] = en
    return out


def load_product_catalog() -> list[dict]:
    """Full shared product catalog as a list of dicts."""
    path = _DATA_DIR / "product_catalog.csv"
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
