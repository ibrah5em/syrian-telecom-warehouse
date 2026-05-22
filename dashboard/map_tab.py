"""
map_tab.py — Coverage Map tab built on a real interactive basemap.

Stack:
  * go.Choroplethmapbox        — choropleth fill on top of a tile basemap
  * mapbox_style="carto-darkmatter" — free CARTO dark tiles, English labels
  * GADM 4.1 Syria admin-1 GeoJSON (14 governorates)
  * Outside-Syria mask layer    — Proton-VPN-style darken-the-neighbours effect

The bundled file dashboard/data/syria_gov.geojson is the GADM level-1 dataset.
If it is absent at startup the module tries to download it from the GADM CDN.

The map is fully pannable / zoomable via standard Mapbox gestures
(drag to pan, scroll/pinch to zoom).
"""
from __future__ import annotations

import json
import logging
import pathlib
import urllib.request

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE         = pathlib.Path(__file__).resolve().parent
_GEOJSON_PATH = _HERE / "data" / "syria_gov.geojson"
_GEOJSON_URL  = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_SYR_1.json"

# ── Colour palette ────────────────────────────────────────────────────────────
_C = {
    "bg":        "#0A0E1A",
    "card":      "#111827",
    "border":    "#1E293B",
    "gold":      "#D4A843",
    "goldLight": "#F5D78E",
    "goldDim":   "#8B7235",
    "text":      "#F1F5F9",
    "textDim":   "#94A3B8",
    "textMuted": "#64748B",
    "syriatel":  "#F59E0B",
    "mtn":       "#3B82F6",
    "green":     "#10B981",
    "purple":    "#8B5CF6",
}

# Diverging heat ramp for the choropleth — low → high revenue
_COLOR_SCALE = [
    [0.00, "#3A2D0B"],
    [0.25, "#5A4818"],
    [0.50, "#8B6B22"],
    [0.75, "#B89033"],
    [1.00, "#F5D78E"],
]
LEGEND_STOPS = [c for _, c in _COLOR_SCALE]


# ── Governorate metadata ──────────────────────────────────────────────────────
GOV_META = [
    {"id": "rif_dimashq", "name": "Rif Dimashq", "ar": "ريف دمشق"},
    {"id": "raqqa",       "name": "Raqqa",        "ar": "الرقة"},
    {"id": "tartus",      "name": "Tartus",        "ar": "طرطوس"},
    {"id": "deir_ez_zor", "name": "Deir ez-Zor",  "ar": "دير الزور"},
    {"id": "idlib",       "name": "Idlib",         "ar": "إدلب"},
    {"id": "latakia",     "name": "Latakia",       "ar": "اللاذقية"},
    {"id": "homs",        "name": "Homs",          "ar": "حمص"},
    {"id": "quneitra",    "name": "Quneitra",      "ar": "القنيطرة"},
    {"id": "as_suwayda",  "name": "As-Suwayda",   "ar": "السويداء"},
    {"id": "aleppo",      "name": "Aleppo",        "ar": "حلب"},
    {"id": "damascus",    "name": "Damascus",      "ar": "دمشق"},
    {"id": "hama",        "name": "Hama",          "ar": "حماة"},
    {"id": "daraa",       "name": "Daraa",         "ar": "درعا"},
    {"id": "al_hasakah",  "name": "Al-Hasakah",   "ar": "الحسكة"},
]

# DW city_df city names → internal gov IDs
CITY_TO_GOV: dict[str, str] = {
    "Damascus":    "damascus",
    "Aleppo":      "aleppo",
    "Homs":        "homs",
    "Hama":        "hama",
    "Latakia":     "latakia",
    "Tartus":      "tartus",
    "Deir ez-Zor": "deir_ez_zor",
    "Raqqa":       "raqqa",
    "Al-Hasakah":  "al_hasakah",
    "Daraa":       "daraa",
    "As-Suwayda":  "as_suwayda",
    "Quneitra":    "quneitra",
    "Idlib":       "idlib",
    "Rif Dimashq": "rif_dimashq",
}

# GADM NAME_1 → internal gov IDs
_GADM_NAME_TO_ID: dict[str, str] = {
    "Aleppo":       "aleppo",
    "AlḤasakah":    "al_hasakah",
    "ArRaqqah":     "raqqa",
    "AsSuwayda'":   "as_suwayda",
    "Damascus":     "damascus",
    "Dar`a":        "daraa",
    "DayrAzZawr":   "deir_ez_zor",
    "Hamah":        "hama",
    "Hims":         "homs",
    "Idlib":        "idlib",
    "Lattakia":     "latakia",
    "Quneitra":     "quneitra",
    "RifDimashq":   "rif_dimashq",
    "Tartus":       "tartus",
}


# ── GeoJSON loader ────────────────────────────────────────────────────────────

def _load_geojson() -> dict:
    """Return parsed GeoJSON; downloads from GADM CDN on first run.

    Each feature is given an `id` equal to our internal gov_id so the choropleth
    can match `locations` against it without needing a `featureidkey`.
    """
    if not _GEOJSON_PATH.exists():
        log.info("Downloading Syria GeoJSON from GADM …")
        _GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(_GEOJSON_URL, _GEOJSON_PATH)
        log.info("Saved %s (%d bytes)", _GEOJSON_PATH, _GEOJSON_PATH.stat().st_size)

    with open(_GEOJSON_PATH, encoding="utf-8") as fh:
        geojson = json.load(fh)

    matched = 0
    for feature in geojson.get("features", []):
        name1 = feature["properties"].get("NAME_1", "")
        gov_id = _GADM_NAME_TO_ID.get(name1)
        if gov_id:
            feature["id"] = gov_id
            matched += 1
        else:
            log.warning("Unrecognised GADM NAME_1: %r", name1)
    log.info("GeoJSON loaded: %d / 14 governorates matched", matched)
    return geojson


_GEOJSON: dict = _load_geojson()


# ── Outside-Syria mask (Proton-VPN-style "darken the neighbours") ─────────────
#
# A single Polygon feature whose outer ring spans the world and whose inner
# rings are every Syria governorate boundary — i.e. Syria itself is punched
# out as a hole. Rendered as a semi-transparent dark fill via mapbox.layers,
# it dims everything outside Syria without affecting the choropleth on top.

def _build_outside_syria_mask() -> dict:
    outer = [[-180, -60], [180, -60], [180, 85], [-180, 85], [-180, -60]]
    holes: list[list] = []
    for feature in _GEOJSON.get("features", []):
        geom = feature.get("geometry", {})
        if geom.get("type") == "Polygon":
            holes.append(geom["coordinates"][0])
        elif geom.get("type") == "MultiPolygon":
            for poly in geom["coordinates"]:
                holes.append(poly[0])
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [outer, *holes],
            },
        }],
    }


_OUTSIDE_MASK: dict = _build_outside_syria_mask()


# ── Data builder ──────────────────────────────────────────────────────────────

def build_gov_data(city_df: pd.DataFrame) -> list[dict]:
    """Merge DW city_df with GOV_META; return list sorted by revenue desc."""
    city_lookup: dict[str, dict] = {}
    for _, row in city_df.iterrows():
        gid = CITY_TO_GOV.get(row["city"])
        if gid:
            city_lookup[gid] = row.to_dict()

    total_nat = float(city_df["total_m"].sum()) if not city_df.empty else 1.0

    result = []
    for meta in GOV_META:
        gid       = meta["id"]
        row       = city_lookup.get(gid, {})
        total_m   = float(row.get("total_m",          0))
        syr_m     = float(row.get("syriatel_m",       0))
        mtn_m     = float(row.get("mtn_m",            0))
        customers = int(row.get("unique_customers",    0))
        orders    = int(row.get("order_count",         0))
        avg_order = (total_m * 1e6 / orders) if orders else 0
        share_pct = (total_m / total_nat * 100) if total_nat else 0
        result.append({
            "id": gid, "name": meta["name"], "ar": meta["ar"],
            "total_m": total_m, "syr_m": syr_m, "mtn_m": mtn_m,
            "customers": customers, "orders": orders,
            "avg_order": avg_order, "share_pct": share_pct,
        })

    result.sort(key=lambda g: g["total_m"], reverse=True)
    for i, g in enumerate(result):
        g["rank"] = i + 1
    return result


# ── Figure builder ────────────────────────────────────────────────────────────

# Initial camera — fits all of Syria
_MAP_CENTER = {"lat": 35.0, "lon": 38.5}
_MAP_ZOOM   = 6.1


def build_map_figure(city_df: pd.DataFrame, selected_id: str | None) -> go.Figure:
    gov_data = build_gov_data(city_df)

    locations  = [g["id"]      for g in gov_data]
    z_values   = [g["total_m"] for g in gov_data]
    customdata = [
        [g["id"], g["name"], g["ar"],
         f"{g['total_m']:.1f}",
         f"{g['syr_m']:.1f}",
         f"{g['mtn_m']:.1f}",
         g["customers"], f"{g['orders']:,}"]
        for g in gov_data
    ]

    hovertemplate = (
        "<b>%{customdata[1]}</b>  %{customdata[2]}<br>"
        "Revenue: <b>%{customdata[3]}M SYP</b><br>"
        "🟡 Syriatel: %{customdata[4]}M  |  🔵 MTN: %{customdata[5]}M<br>"
        "👥 %{customdata[6]} customers  📦 %{customdata[7]} orders"
        "<extra></extra>"
    )

    # Base choropleth layer — all 14 governorates coloured by revenue.
    # Opacity is constant across selection states so updating the highlight
    # trace via dash.Patch does not visibly flicker every polygon.
    base_layer = go.Choroplethmapbox(
        geojson=_GEOJSON,
        locations=locations,
        z=z_values,
        customdata=customdata,
        colorscale=_COLOR_SCALE,
        zmin=0,
        zmax=max(z_values) if z_values else 1,
        marker=dict(
            line=dict(color="#263040", width=0.8),
            opacity=0.78,
        ),
        hovertemplate=hovertemplate,
        showscale=False,
        name="Revenue",
    )

    # Highlight layer — always present so the selection update is a pure
    # data swap (dash.Patch on data[1].locations / z) instead of a full
    # figure rebuild. Empty arrays = nothing selected.
    sel = next((g for g in gov_data if g["id"] == selected_id), None) if selected_id else None
    if sel is not None:
        hl_locations  = [sel["id"]]
        hl_z          = [sel["total_m"]]
        hl_customdata = [customdata[locations.index(sel["id"])]]
    else:
        hl_locations, hl_z, hl_customdata = [], [], []

    highlight_layer = go.Choroplethmapbox(
        geojson=_GEOJSON,
        locations=hl_locations,
        z=hl_z,
        customdata=hl_customdata,
        colorscale=[[0, _C["gold"]], [1, _C["gold"]]],
        zmin=0,
        zmax=max(z_values) if z_values else 1,
        marker=dict(
            line=dict(color=_C["goldLight"], width=3),
            opacity=0.92,
        ),
        hovertemplate=hovertemplate,
        showscale=False,
        name="Selected",
    )

    traces: list[go.BaseTraceType] = [base_layer, highlight_layer]

    layout = go.Layout(
        paper_bgcolor=_C["card"],
        plot_bgcolor=_C["card"],
        margin=dict(t=0, b=0, l=0, r=0),
        height=560,
        mapbox=dict(
            style="carto-darkmatter",     # dark mode, English labels, free
            center=_MAP_CENTER,
            zoom=_MAP_ZOOM,
            uirevision="coverage-map-mapbox",  # keep subplot/tile state across updates
            layers=[
                # Darken everything outside Syria so the country pops
                dict(
                    source=_OUTSIDE_MASK,
                    type="fill",
                    below="traces",
                    color="rgba(6,10,20,0.55)",
                ),
                # Soft outline around the country boundary
                dict(
                    source=_OUTSIDE_MASK,
                    type="line",
                    below="traces",
                    color="rgba(212,168,67,0.35)",
                    line=dict(width=0.8),
                ),
            ],
        ),
        hoverlabel=dict(
            bgcolor="#1F2937",
            bordercolor=_C["gold"],
            font=dict(color=_C["text"], size=12),
        ),
        uirevision="coverage-map",  # preserves zoom/pan across callbacks
    )

    return go.Figure(data=traces, layout=layout)


# ── Panel components ──────────────────────────────────────────────────────────

def _op_bar(name: str, val: float, total: float, color: str) -> html.Div:
    pct = val / total * 100 if total else 50
    return html.Div([
        html.Div([
            html.Span(name, style={"fontSize": 11, "fontWeight": 600, "color": color}),
            html.Span(f"{val:.1f}M ({pct:.1f}%)",
                      style={"fontSize": 11, "color": _C["textDim"]}),
        ], style={"display": "flex", "justifyContent": "space-between"}),
        html.Div(html.Div(style={
            "height": "100%", "borderRadius": 4,
            "background": f"linear-gradient(90deg, {color}, {color}80)",
            "width": f"{pct:.1f}%",
        }), style={"height": 7, "background": _C["bg"],
                   "borderRadius": 4, "overflow": "hidden", "marginTop": 4}),
    ], style={"marginBottom": 10})


def _kpi_cell(label: str, value: str) -> html.Div:
    return html.Div([
        html.Div(label, style={"fontSize": 9, "color": _C["textMuted"],
                               "textTransform": "uppercase"}),
        html.Div(value, style={"fontSize": 15, "fontWeight": 700,
                               "color": _C["text"], "marginTop": 3}),
    ], style={
        "background": "rgba(255,255,255,0.02)",
        "border": f"1px solid {_C['border']}",
        "borderRadius": 8, "padding": "10px 12px",
    })


def gov_detail_panel(gov: dict, _gov_data: list) -> html.Div:
    return html.Div([
        # Header
        html.Div([
            html.Div([
                html.Div(gov["name"],
                         style={"fontSize": 18, "fontWeight": 700, "color": _C["gold"]}),
                html.Div(gov["ar"], style={
                    "fontSize": 15, "color": _C["goldDim"],
                    "fontFamily": "'Noto Kufi Arabic', serif", "direction": "rtl",
                }),
            ]),
            html.Div("Click again to deselect", style={
                "fontSize": 10, "color": _C["textMuted"],
                "fontStyle": "italic", "textAlign": "right",
            }),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "flex-start", "marginBottom": 18}),

        # Revenue hero
        html.Div([
            html.Div("Total Revenue", style={
                "fontSize": 10, "color": _C["textMuted"],
                "textTransform": "uppercase", "letterSpacing": "0.1em",
            }),
            html.Div([
                html.Span(f"{gov['total_m']:.1f}M",
                          style={"fontSize": 30, "fontWeight": 700, "color": _C["gold"]}),
                html.Span(" SYP", style={"fontSize": 13, "color": _C["textDim"]}),
            ]),
            html.Div(f"{gov['share_pct']:.1f}% of national revenue",
                     style={"fontSize": 11, "color": _C["textMuted"], "marginTop": 2}),
        ], style={
            "background": f"linear-gradient(135deg, {_C['gold']}12, transparent)",
            "borderRadius": 10, "padding": "16px 18px", "marginBottom": 18,
            "border": f"1px solid {_C['gold']}18",
        }),

        # KPI 2×2
        html.Div([
            _kpi_cell("Customers", f"👥 {gov['customers']:,}"),
            _kpi_cell("Orders",    f"📦 {gov['orders']:,}"),
            _kpi_cell("Avg Order", f"📊 {gov['avg_order']/1e3:.0f}K SYP"),
            _kpi_cell("Rev Share", f"📈 {gov['share_pct']:.1f}%"),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                  "gap": 10, "marginBottom": 18}),

        # Operator split
        html.Div([
            html.Div("Operator Split", style={
                "fontSize": 11, "color": _C["textMuted"], "marginBottom": 10,
                "textTransform": "uppercase", "letterSpacing": "0.05em",
            }),
            _op_bar("Syriatel",  gov["syr_m"], gov["total_m"], _C["syriatel"]),
            _op_bar("MTN Syria", gov["mtn_m"], gov["total_m"], _C["mtn"]),
        ], style={"marginBottom": 16}),

        # National rank badge
        html.Div([
            html.Div([
                html.Div("National Rank",
                         style={"fontSize": 10, "color": _C["textMuted"]}),
                html.Div("الترتيب الوطني", style={
                    "fontSize": 10, "color": _C["goldDim"],
                    "fontFamily": "'Noto Kufi Arabic', serif",
                }),
            ]),
            html.Div([
                html.Span(f"#{gov['rank']}",
                          style={"fontSize": 26, "fontWeight": 700, "color": _C["purple"]}),
                html.Span(" / 14", style={"fontSize": 11, "color": _C["textMuted"]}),
            ]),
        ], style={
            "background": f"{_C['purple']}0D",
            "border": f"1px solid {_C['purple']}20",
            "borderRadius": 8, "padding": "10px 14px",
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        }),
    ], style={
        "background": _C["card"],
        "border": f"1px solid {_C['gold']}30",
        "borderRadius": 14, "padding": 22,
    })


def gov_ranking_panel(gov_data: list) -> html.Div:
    max_rev = gov_data[0]["total_m"] if gov_data else 1

    rows = []
    for i, g in enumerate(gov_data):
        bar_w   = g["total_m"] / max_rev * 100 if max_rev else 0
        syr_pct = g["syr_m"] / g["total_m"] * 100 if g["total_m"] else 50

        rows.append(html.Button([
            html.Span(str(i + 1), style={
                "width": 22, "height": 22, "borderRadius": 5,
                "background": f"{_C['gold']}18" if i < 3 else "rgba(255,255,255,0.03)",
                "color": _C["gold"] if i < 3 else _C["textMuted"],
                "fontSize": 10, "fontWeight": 700,
                "display": "inline-flex", "alignItems": "center",
                "justifyContent": "center", "flexShrink": 0,
            }),
            html.Div([
                html.Div(g["name"], style={"fontSize": 11, "fontWeight": 600,
                                           "color": _C["text"], "textAlign": "left"}),
                html.Div(g["ar"],   style={"fontSize": 9, "color": _C["goldDim"],
                                           "fontFamily": "'Noto Kufi Arabic', serif"}),
            ], style={"flex": 1, "minWidth": 0}),
            html.Span(f"{g['total_m']:.1f}M",
                      style={"fontSize": 12, "fontWeight": 700,
                             "color": _C["text"], "flexShrink": 0}),
            html.Div(html.Div(style={
                "height": "100%", "borderRadius": 3,
                "background": (
                    f"linear-gradient(90deg, {_C['syriatel']} {syr_pct:.0f}%,"
                    f" {_C['mtn']} {syr_pct:.0f}%)"
                ),
                "width": f"{bar_w:.0f}%",
            }), style={"width": 44, "height": 5, "background": _C["bg"],
                       "borderRadius": 3, "overflow": "hidden", "flexShrink": 0}),
        ],
        id={"type": "gov-rank-row", "index": g["id"]},
        n_clicks=0,
        style={
            "display": "flex", "alignItems": "center", "gap": 8,
            "padding": "6px 8px", "borderRadius": 6, "cursor": "pointer",
            "width": "100%", "background": "transparent",
            "border": "none", "color": "inherit",
        }))

    total_m = sum(g["total_m"]   for g in gov_data)
    total_c = sum(g["customers"] for g in gov_data)
    top_gov = gov_data[0]["name"] if gov_data else "—"

    summary = [
        ("Total Revenue",   f"{total_m:.1f}M SYP", _C["gold"]),
        ("Total Customers", f"{total_c:,}",         _C["green"]),
        ("Governorates",    "14 covered",           _C["purple"]),
        ("Top Region",      top_gov,                _C["syriatel"]),
    ]

    return html.Div([
        html.Div([
            html.Div("Revenue Ranking", style={
                "fontSize": 13, "fontWeight": 600,
                "color": _C["textDim"], "marginBottom": 2,
            }),
            html.Div("ترتيب الإيرادات", style={
                "fontSize": 11, "color": _C["goldDim"],
                "fontFamily": "'Noto Kufi Arabic', serif",
                "direction": "rtl", "marginBottom": 14,
            }),
            html.Div(rows),
        ], style={
            "background": _C["card"], "border": f"1px solid {_C['border']}",
            "borderRadius": 14, "padding": 18, "marginBottom": 14,
        }),

        html.Div([
            html.Div("National Summary", style={
                "fontSize": 12, "fontWeight": 600,
                "color": _C["textDim"], "marginBottom": 10,
            }),
            *[html.Div([
                html.Span(lbl, style={"fontSize": 11, "color": _C["textMuted"]}),
                html.Span(val, style={"fontSize": 12, "fontWeight": 600, "color": clr}),
            ], style={
                "display": "flex", "justifyContent": "space-between", "padding": "6px 0",
                "borderBottom": f"1px solid {_C['border']}" if j < 3 else "none",
            }) for j, (lbl, val, clr) in enumerate(summary)],
        ], style={
            "background": _C["card"], "border": f"1px solid {_C['border']}",
            "borderRadius": 14, "padding": 18,
        }),
    ])


# ── Tab layout ────────────────────────────────────────────────────────────────

def coverage_map_tab(data: dict) -> html.Div:
    city_df  = data["city"]
    gov_data = build_gov_data(city_df)

    return html.Div([
        # Header
        html.Div([
            html.Div([
                html.H2("Interactive Coverage Map",
                        style={"fontSize": 22, "fontWeight": 700, "margin": 0}),
                html.Span("خريطة التغطية التفاعلية", style={
                    "fontSize": 16, "color": _C["goldDim"],
                    "fontFamily": "'Noto Kufi Arabic', serif", "direction": "rtl",
                }),
            ], style={"display": "flex", "alignItems": "baseline",
                      "gap": 16, "flexWrap": "wrap"}),
            html.P(
                "Revenue heatmap across 14 Syrian governorates on an OpenStreetMap basemap — "
                "drag to pan, scroll to zoom, click any region for a detailed breakdown",
                style={"fontSize": 13, "color": _C["textMuted"], "margin": "6px 0 0"},
            ),
            html.Div(style={
                "width": 60, "height": 3,
                "background": f"linear-gradient(90deg, {_C['gold']}, transparent)",
                "borderRadius": 2, "marginTop": 10,
            }),
        ], style={"marginBottom": 24}),

        # Legend bar
        html.Div([
            html.Span("Revenue Intensity:",
                      style={"fontSize": 12, "color": _C["textMuted"]}),
            html.Div([
                html.Div(style={
                    "width": 32, "height": 12, "background": c,
                    "borderRadius": (
                        "3px 0 0 3px" if j == 0 else
                        "0 3px 3px 0" if j == len(LEGEND_STOPS) - 1 else "0"
                    ),
                })
                for j, c in enumerate(LEGEND_STOPS)
            ], style={"display": "flex"}),
            html.Span("Low → High",
                      style={"fontSize": 11, "color": _C["textMuted"]}),
            html.Div(style={"flex": 1}),
            html.Span("🟡 Syriatel",
                      style={"fontSize": 12, "color": _C["textDim"]}),
            html.Span("🔵 MTN Syria",
                      style={"fontSize": 12, "color": _C["textDim"]}),
        ], style={
            "display": "flex", "alignItems": "center", "gap": 20,
            "marginBottom": 20, "padding": "10px 18px",
            "background": _C["card"], "border": f"1px solid {_C['border']}",
            "borderRadius": 10, "flexWrap": "wrap",
        }),

        # Shared selection store
        dcc.Store(id="map-selected-gov", data=None),

        # Map + right panel — CSS grid with fixed-track columns. Using grid
        # (not flex) means the right column's content swap can't change the
        # map column's width, so dcc.Graph never receives a resize → Plotly
        # never re-renders the mapbox subplot → no tile flicker on click.
        html.Div([
            html.Div([
                dcc.Graph(
                    id="coverage-map-graph",
                    figure=build_map_figure(city_df, None),
                    config={
                        "displayModeBar": True,
                        "scrollZoom": True,
                        "displaylogo": False,
                        "modeBarButtonsToRemove": [
                            "lasso2d", "select2d", "toImage",
                        ],
                        "responsive": True,
                    },
                    style={"width": "100%", "height": "560px"},
                    responsive=True,
                ),
            ], style={
                "background": _C["card"],
                "border": f"1px solid {_C['border']}",
                "borderRadius": 18, "padding": 6,
                "minWidth": 0,
                "overflow": "hidden",
            }),

            html.Div(
                id="map-right-panel",
                children=gov_ranking_panel(gov_data),
                style={
                    "minWidth": 0,
                    "overflowY": "auto", "maxHeight": 600,
                },
            ),
        ], style={
            "display": "grid",
            "gridTemplateColumns": "minmax(360px, 1fr) 320px",
            "gap": 20,
            "alignItems": "start",
        }),
    ])
