"""Transform customer data from both operators into a unified dim_customer shape.

Divergence resolved here:
  - Phone format: MTN 0XXXXXXXXX → E.164 +963XXXXXXXXX
  - City language: Syriatel Arabic → canonical English via city map
  - Table naming: customers / clients → unified source_system + source_customer_id
"""
from __future__ import annotations

import re
from typing import NamedTuple

import pandas as pd

from etl.utils.logging import get_logger
from etl.utils.mappings import load_city_map_ar_to_en, load_city_map_en_to_canonical

logger = get_logger(__name__)

_E164_RE    = re.compile(r'^\+9639\d{8}$')
_NATIONAL_RE = re.compile(r'^09\d{8}$')

_DIM_COLS = [
    "source_system", "source_customer_id",
    "full_name", "phone_e164", "city", "signup_date",
]


class CustomerResult(NamedTuple):
    records: pd.DataFrame    # rows ready for upsert into dim_customer
    quarantine: list[dict]   # rows that failed — written to etl_errors


def _normalize_phone(raw: str, source: str) -> str:
    s = re.sub(r'\s+', '', raw).strip()
    if source == "SYRIATEL":
        if _E164_RE.match(s):
            return s
        raise ValueError(f"invalid E.164 phone for SYRIATEL: {raw!r}")
    else:  # MTN
        if _NATIONAL_RE.match(s):
            return "+963" + s[1:]
        raise ValueError(f"invalid national phone for MTN: {raw!r}")


def _transform_syriatel(df: pd.DataFrame, city_ar_to_en: dict[str, str]) -> tuple[list[dict], list[dict]]:
    good: list[dict] = []
    bad: list[dict] = []
    for row in df.itertuples(index=False):
        try:
            city_en = city_ar_to_en.get(row.city_ar)
            if city_en is None:
                raise ValueError(f"unknown Arabic city: {row.city_ar!r}")
            phone = _normalize_phone(row.phone, "SYRIATEL")
            good.append({
                "source_system":      "SYRIATEL",
                "source_customer_id": str(row.customer_id),
                "full_name":          row.full_name,
                "phone_e164":         phone,
                "city":               city_en,
                "signup_date":        row.signup_date,
            })
        except ValueError as exc:
            bad.append({
                "source_system": "SYRIATEL",
                "source_table":  "customers",
                "source_row":    dict(zip(df.columns, row)),
                "reason":        str(exc),
            })
    return good, bad


def _transform_mtn(df: pd.DataFrame, city_en_canonical: dict[str, str]) -> tuple[list[dict], list[dict]]:
    good: list[dict] = []
    bad: list[dict] = []
    for row in df.itertuples(index=False):
        try:
            city = city_en_canonical.get(row.city_en)
            if city is None:
                raise ValueError(f"unknown English city: {row.city_en!r}")
            phone = _normalize_phone(row.msisdn, "MTN")
            good.append({
                "source_system":      "MTN",
                "source_customer_id": str(row.client_id),
                "full_name":          row.client_name,
                "phone_e164":         phone,
                "city":               city,
                "signup_date":        row.registered_at,
            })
        except ValueError as exc:
            bad.append({
                "source_system": "MTN",
                "source_table":  "clients",
                "source_row":    dict(zip(df.columns, row)),
                "reason":        str(exc),
            })
    return good, bad


def transform(syr_data: dict, mtn_data: dict) -> CustomerResult:
    city_ar_to_en     = load_city_map_ar_to_en()
    city_en_canonical = load_city_map_en_to_canonical()

    syr_good, syr_bad = _transform_syriatel(syr_data["customers"], city_ar_to_en)
    mtn_good, mtn_bad = _transform_mtn(mtn_data["clients"], city_en_canonical)

    all_good = syr_good + mtn_good
    all_bad  = syr_bad  + mtn_bad

    logger.info(
        "transform.customers: %d ok, %d quarantined "
        "(syr: %d ok / %d bad  |  mtn: %d ok / %d bad)",
        len(all_good), len(all_bad),
        len(syr_good), len(syr_bad),
        len(mtn_good), len(mtn_bad),
    )

    return CustomerResult(
        records=pd.DataFrame(all_good, columns=_DIM_COLS) if all_good else pd.DataFrame(columns=_DIM_COLS),
        quarantine=all_bad,
    )
