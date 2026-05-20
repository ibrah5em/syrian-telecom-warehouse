"""
app.py — Dash entry point for the Syrian Telecom Data Warehouse dashboard.

Run locally (requires a reachable DW):
    DATABASE_URL=postgresql://postgres:postgres@localhost:5435/telecom_dw python app.py

In Docker Compose the DATABASE_URL defaults to the telecom_dw service hostname.
"""

import logging
import os

import dash
from dash import Input, Output, dcc, html

import components as comp
from data import load_all_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    title="Telecom DW — Syria",
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"charset": "utf-8"},
    ],
)
server = app.server  # expose Flask server for gunicorn

log.info("Loading warehouse data…")
DATA = load_all_data()
if DATA is None:
    log.error("Could not load data from the warehouse — dashboard will show error state")

# ---------------------------------------------------------------------------
# Tab definitions
# ---------------------------------------------------------------------------

TABS = [
    {"id": "overview",        "label": "Overview",           "label_ar": "نظرة عامة",       "icon": "📊"},
    {"id": "revenue",         "label": "Revenue Analysis",   "label_ar": "تحليل الإيرادات",   "icon": "💰"},
    {"id": "geo",             "label": "Geographic",         "label_ar": "التوزيع الجغرافي",  "icon": "🗺️"},
    {"id": "customers",       "label": "Customer Segments",  "label_ar": "شرائح العملاء",    "icon": "👥"},
    {"id": "forecast",        "label": "Forecast & Mining",  "label_ar": "التنبؤ والتنقيب",   "icon": "🔮"},
    {"id": "recommendations", "label": "Recommendations",    "label_ar": "التوصيات",          "icon": "📋"},
]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

BG   = "#0A0E1A"
CARD = "#111827"
BORD = "#1E293B"
GOLD = "#D4A843"
GOLD_DIM = "#8B7235"
TEXT_DIM  = "#94A3B8"
TEXT_MUTED = "#64748B"


def _header() -> html.Header:
    return html.Header([
        html.Div([
            html.Div([
                html.Div("DW", className="dw-logo"),
                html.Div([
                    html.H1("Telecom Data Warehouse", className="dw-title-en"),
                    html.Div("مستودع بيانات الاتصالات السورية الموحد", className="dw-title-ar"),
                ]),
            ], style={"display": "flex", "alignItems": "center", "gap": 16}),

            html.Div([
                html.Div([
                    html.Div("Ministry of Communications",
                             style={"fontSize": 11, "color": TEXT_MUTED,
                                    "textTransform": "uppercase", "letterSpacing": "0.1em",
                                    "textAlign": "right"}),
                    html.Div("وزارة الاتصالات والتقانة",
                             style={"fontSize": 11, "color": GOLD_DIM,
                                    "fontFamily": "'Noto Kufi Arabic', sans-serif",
                                    "direction": "rtl", "textAlign": "right"}),
                ]),
                html.Div(className="live-dot"),
            ], style={"display": "flex", "alignItems": "center", "gap": 16}),
        ], className="dw-header-inner"),
    ], className="dw-header")


def _tab_nav() -> html.Div:
    return html.Div([
        dcc.Tabs(
            id="tabs",
            value="overview",
            className="custom-tabs",
            children=[
                dcc.Tab(
                    label=f"{t['icon']}  {t['label']}",
                    value=t["id"],
                    className="custom-tab",
                    selected_className="custom-tab--selected",
                )
                for t in TABS
            ],
        ),
    ], className="tab-nav-outer")


app.layout = html.Div([
    _header(),
    _tab_nav(),
    html.Main(id="tab-content", className="main-content"),
    html.Footer([
        html.Span("Telecom DW — Unified Data Warehouse"),
        html.Span(" | ", style={"margin": "0 12px", "color": BORD}),
        html.Span("الجمهورية العربية السورية",
                  style={"fontFamily": "'Noto Kufi Arabic', sans-serif"}),
        html.Span(" | ", style={"margin": "0 12px", "color": BORD}),
        html.Span(id="footer-stats", children="—"),
    ], style={
        "borderTop": f"1px solid {BORD}", "padding": "20px 32px",
        "textAlign": "center", "color": TEXT_MUTED, "fontSize": 12,
        "background": CARD,
    }),
], style={"background": BG, "minHeight": "100vh", "color": "#F1F5F9"})


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(Output("tab-content", "children"), Input("tabs", "value"))
def render_tab(tab: str) -> html.Div:
    if DATA is None:
        return html.Div([
            html.Div("⚠️", style={"fontSize": 48, "marginBottom": 16}),
            html.H2("Cannot connect to the data warehouse",
                    style={"color": "#EF4444", "marginBottom": 8}),
            html.P(
                "Ensure the telecom_dw PostgreSQL container is running and reachable.",
                style={"color": TEXT_MUTED, "fontSize": 13},
            ),
            html.Code(
                f"DATABASE_URL = {os.getenv('DATABASE_URL', 'postgresql://dw:dw@dw:5432/telecom_dw')}",
                style={"fontSize": 11, "color": GOLD_DIM, "display": "block", "marginTop": 16},
            ),
        ], style={
            "textAlign": "center", "padding": "80px 32px",
            "color": "#F1F5F9",
        })

    if tab == "overview":
        return comp.overview_tab(DATA)
    if tab == "revenue":
        return comp.revenue_tab(DATA)
    if tab == "geo":
        return comp.geo_tab(DATA)
    if tab == "customers":
        return comp.customers_tab(DATA)
    if tab == "forecast":
        return comp.forecast_tab(DATA)
    if tab == "recommendations":
        return comp.recommendations_tab(DATA)
    return html.Div("Unknown tab", style={"color": "#EF4444"})


@app.callback(Output("footer-stats", "children"), Input("tabs", "value"))
def update_footer(_tab: str) -> str:
    if DATA is None:
        return "No data loaded"
    return (
        f"{DATA['total_orders']:,} orders · "
        f"{DATA['total_customers']:,} customers · "
        f"{DATA['cities_served']} cities · "
        f"{len(DATA['products'])} products"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8050))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    log.info("Starting Dash server on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
