"""Smoke tests for reference-data mappings. Run: pytest etl/tests/test_mappings.py"""
from etl.utils.mappings import (
    load_city_map_ar_to_en,
    load_product_catalog,
)


def test_city_map_covers_canonical_governorates():
    m = load_city_map_ar_to_en()
    # 14 official governorates plus a few sub-city entries we generate orders for
    assert len(m) >= 14, f"Expected at least 14 governorates, got {len(m)}"
    assert m["دمشق"] == "Damascus"
    assert m["حلب"] == "Aleppo"
    assert m["اللاذقية"] == "Latakia"


def test_product_catalog_has_15_offerings():
    rows = load_product_catalog()
    assert len(rows) == 15
    # spot-check first and last
    assert rows[0]["syriatel_name_ar"].startswith("باقة")
    assert rows[0]["mtn_name_en"].endswith("Bundle")


def test_product_catalog_prices_match_across_operators():
    """Syriatel and MTN price the same offering identically."""
    rows = load_product_catalog()
    for r in rows:
        assert int(r["syriatel_price_int"]) == int(float(r["mtn_price_decimal"])), \
            f"Offering {r['offering_id']}: prices differ across operators"


def test_product_catalog_categories_diverge_by_case():
    """Syriatel uses Title case, MTN uses UPPER — the Divergence Rule."""
    rows = load_product_catalog()
    for r in rows:
        assert r["category"][0].isupper() and r["category"][1:].islower(), \
            f"Syriatel category must be Title Case: {r['category']!r}"
        assert r["mtn_category"].isupper(), \
            f"MTN category must be UPPER: {r['mtn_category']!r}"
