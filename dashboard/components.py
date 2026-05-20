"""
components.py — Reusable Plotly figures and Dash HTML component builders.
All chart functions accept DataFrames and return plotly.graph_objects.Figure.
All layout helpers return dash html.Div subtrees.
"""

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc

# ---------------------------------------------------------------------------
# Colour palette (mirrors JSX reference)
# ---------------------------------------------------------------------------
C = {
    "bg":       "#0A0E1A",
    "card":     "#111827",
    "border":   "#1E293B",
    "gold":     "#D4A843",
    "goldDim":  "#8B7235",
    "accent1":  "#3B82F6",   # blue  — MTN
    "accent2":  "#F59E0B",   # amber — Syriatel
    "accent3":  "#10B981",   # green
    "accent4":  "#EF4444",   # red
    "accent5":  "#8B5CF6",   # purple
    "text":     "#F1F5F9",
    "textDim":  "#94A3B8",
    "textMuted": "#64748B",
}

COMPANY_COLORS = {"SYRIATEL": C["accent2"], "MTN": C["accent1"]}

# ---------------------------------------------------------------------------
# Plotly base layout
# ---------------------------------------------------------------------------

def _base_layout(height: int = 300, margin: dict | None = None) -> dict:
    m = margin or dict(t=16, b=40, l=50, r=16)
    return dict(
        height=height,
        autosize=True,
        paper_bgcolor=C["card"],
        plot_bgcolor=C["card"],
        font=dict(color=C["textMuted"], family="DM Sans, sans-serif", size=11),
        margin=m,
        xaxis=dict(
            gridcolor=C["border"],
            linecolor="rgba(0,0,0,0)",
            tickcolor="rgba(0,0,0,0)",
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor=C["border"],
            linecolor="rgba(0,0,0,0)",
            tickcolor="rgba(0,0,0,0)",
            zeroline=False,
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=C["textDim"], size=11),
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left",   x=0,
        ),
        hoverlabel=dict(
            bgcolor="#1F2937",
            bordercolor=C["border"],
            font=dict(color=C["text"], size=12),
        ),
    )


def _fig(traces, layout_overrides: dict | None = None, height: int = 300) -> go.Figure:
    layout = _base_layout(height)
    if layout_overrides:
        layout.update(layout_overrides)
    fig = go.Figure(data=traces, layout=go.Layout(**layout))
    fig.update_layout(uirevision="constant")
    return fig


# ---------------------------------------------------------------------------
# HTML building blocks
# ---------------------------------------------------------------------------

def section_title(title: str, title_ar: str, subtitle: str = "") -> html.Div:
    return html.Div([
        html.Div([
            html.H2(title, className="section-title-en"),
            html.Span(title_ar, className="section-title-ar arabic"),
        ], style={"display": "flex", "alignItems": "baseline", "flexWrap": "wrap"}),
        html.P(subtitle, className="section-subtitle") if subtitle else None,
        html.Div(className="section-divider"),
    ], className="section-title-wrap")


def chart_card(children, style: dict | None = None) -> html.Div:
    s = {"background": C["card"], "border": f"1px solid {C['border']}",
         "borderRadius": 16, "padding": 24}
    if style:
        s.update(style)
    return html.Div(children, style=s)


def chart_header(title_en: str, title_ar: str) -> list:
    return [
        html.Div(title_en, className="chart-title-en"),
        html.Div(title_ar, className="chart-title-ar arabic"),
    ]


def kpi_card(label: str, label_ar: str, value: str, icon: str, color: str, delay: float = 0) -> html.Div:
    return html.Div([
        html.Div(style={
            "position": "absolute", "top": -20, "right": -20,
            "width": 80, "height": 80, "borderRadius": "50%",
            "background": color, "opacity": 0.07,
        }),
        html.Div(label, className="kpi-label-en"),
        html.Div(label_ar, className="kpi-label-ar"),
        html.Div(value, className="kpi-value", style={"color": C["text"]}),
        html.Div(icon, className="kpi-icon"),
    ], className="kpi-card", style={"animationDelay": f"{delay}s"})


def legend_item(color: str, label: str) -> html.Div:
    return html.Div([
        html.Div(style={"width": 10, "height": 10, "borderRadius": 3, "background": color, "flexShrink": 0}),
        html.Span(label, style={"fontSize": 11, "color": C["textDim"]}),
    ], className="legend-row")


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def _fmt_m(v: float, decimals: int = 1) -> str:
    return f"{v:.{decimals}f}M SYP"


def _fmt_k(v: float) -> str:
    return f"{v/1000:.0f}K"


# ---------------------------------------------------------------------------
# 1. Company market share donut
# ---------------------------------------------------------------------------

def company_share_pie(company_df: pd.DataFrame) -> go.Figure:
    colors = [COMPANY_COLORS.get(c, C["gold"]) for c in company_df["company_code"]]
    trace = go.Pie(
        labels=company_df["company_name_en"],
        values=company_df["share_pct"],
        hole=0.6,
        marker=dict(colors=colors, line=dict(color=C["card"], width=3)),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>%{value:.1f}% market share<extra></extra>",
    )
    layout_ov = dict(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
    return _fig([trace], layout_ov, height=250)


# ---------------------------------------------------------------------------
# 2. Monthly area chart
# ---------------------------------------------------------------------------

def monthly_area_chart(monthly_wide: pd.DataFrame) -> go.Figure:
    traces = []
    for code, color, fill_color in [
        ("SYRIATEL", C["accent2"], "rgba(245,158,11,0.2)"),
        ("MTN",      C["accent1"], "rgba(59,130,246,0.2)"),
    ]:
        col = code if code in monthly_wide.columns else None
        if col is None:
            continue
        name = "Syriatel" if code == "SYRIATEL" else "MTN Syria"
        traces.append(go.Scatter(
            x=monthly_wide["label"],
            y=monthly_wide[col],
            mode="lines",
            name=name,
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate=f"<b>{name}</b><br>%{{y:.1f}}M SYP<extra></extra>",
        ))
    layout_ov = dict(yaxis=dict(ticksuffix="M", gridcolor=C["border"]))
    return _fig(traces, layout_ov, height=260)


# ---------------------------------------------------------------------------
# 3. Monthly grouped bar chart
# ---------------------------------------------------------------------------

def monthly_bar_chart(monthly_wide: pd.DataFrame) -> go.Figure:
    traces = []
    for code, color in [("SYRIATEL", C["accent2"]), ("MTN", C["accent1"])]:
        col = code if code in monthly_wide.columns else None
        if col is None:
            continue
        name = "Syriatel" if code == "SYRIATEL" else "MTN Syria"
        traces.append(go.Bar(
            x=monthly_wide["label"],
            y=monthly_wide[col],
            name=name,
            marker=dict(color=color, line=dict(width=0)),
            hovertemplate=f"<b>{name}</b><br>%{{y:.1f}}M SYP<extra></extra>",
        ))
    layout_ov = dict(
        barmode="group",
        bargap=0.25,
        bargroupgap=0.05,
        yaxis=dict(ticksuffix="M", gridcolor=C["border"]),
    )
    return _fig(traces, layout_ov, height=340)


# ---------------------------------------------------------------------------
# 4. City stacked horizontal bar
# ---------------------------------------------------------------------------

def city_revenue_bar(city_df: pd.DataFrame) -> go.Figure:
    df = city_df.sort_values("total_m", ascending=True)
    traces = [
        go.Bar(
            y=df["city"],
            x=df["syriatel_m"],
            name="Syriatel",
            orientation="h",
            marker=dict(color=C["accent2"], line=dict(width=0)),
            hovertemplate="<b>%{y}</b><br>Syriatel: %{x:.1f}M SYP<extra></extra>",
        ),
        go.Bar(
            y=df["city"],
            x=df["mtn_m"],
            name="MTN Syria",
            orientation="h",
            marker=dict(color=C["accent1"], line=dict(width=0)),
            hovertemplate="<b>%{y}</b><br>MTN: %{x:.1f}M SYP<extra></extra>",
        ),
    ]
    layout_ov = dict(
        barmode="stack",
        bargap=0.25,
        xaxis=dict(ticksuffix="M", gridcolor=C["border"]),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11, color=C["textDim"])),
        margin=dict(t=16, b=40, l=110, r=16),
    )
    return _fig(traces, layout_ov, height=440)


# ---------------------------------------------------------------------------
# 5. Product catalog horizontal bar
# ---------------------------------------------------------------------------

def product_bar_chart(products_df: pd.DataFrame) -> go.Figure:
    df = products_df.sort_values("avg_price_syp", ascending=True).head(12)
    cat_colors = {"INTERNET": C["accent1"], "VOICE": C["accent3"], "BUNDLE": C["accent2"]}
    colors = [cat_colors.get(c, C["gold"]) for c in df["category"]]

    trace = go.Bar(
        y=df["name"],
        x=df["avg_price_syp"],
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        hovertemplate="<b>%{y}</b><br>%{x:,.0f} SYP avg<extra></extra>",
    )
    layout_ov = dict(
        showlegend=False,
        xaxis=dict(gridcolor=C["border"], tickformat=",.0f"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11, color=C["textDim"])),
        margin=dict(t=16, b=40, l=150, r=16),
    )
    return _fig([trace], layout_ov, height=340)


# ---------------------------------------------------------------------------
# 6. RFM segment pie
# ---------------------------------------------------------------------------

def rfm_pie_chart(rfm_summary: pd.DataFrame) -> go.Figure:
    trace = go.Pie(
        labels=rfm_summary["segment"],
        values=rfm_summary["count"],
        marker=dict(
            colors=rfm_summary["color"].tolist(),
            line=dict(color=C["card"], width=3),
        ),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>%{value} customers (%{percent})<extra></extra>",
    )
    layout_ov = dict(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
    return _fig([trace], layout_ov, height=300)


# ---------------------------------------------------------------------------
# 7. Forecast line chart
# ---------------------------------------------------------------------------

def forecast_chart(monthly_wide: pd.DataFrame, forecast: dict) -> go.Figure:
    traces = []

    # Actual lines (solid, from monthly_wide which covers all history)
    for code, color in [("SYRIATEL", C["accent2"]), ("MTN", C["accent1"])]:
        col = code if code in monthly_wide.columns else None
        if col is None:
            continue
        name = "Syriatel" if code == "SYRIATEL" else "MTN"
        traces.append(go.Scatter(
            x=monthly_wide["label"],
            y=monthly_wide[col],
            mode="lines+markers",
            name=f"{name} (actual)",
            line=dict(color=color, width=2.5),
            marker=dict(size=5, color=color),
            hovertemplate=f"<b>{name} actual</b><br>%{{y:.1f}}M SYP<extra></extra>",
        ))

    # Fitted lines (faint dashed) — present when data comes from the pre-computed CSV
    for code, color in [("SYRIATEL", C["accent2"]), ("MTN", C["accent1"])]:
        if code not in forecast:
            continue
        fitted = forecast[code].get("fitted")
        if fitted is None or (hasattr(fitted, "empty") and fitted.empty):
            continue
        name = "Syriatel" if code == "SYRIATEL" else "MTN"
        traces.append(go.Scatter(
            x=[d.strftime("%b %y") for d in fitted.index],
            y=[float(v) / 1e6 for v in fitted.values],
            mode="lines",
            name=f"{name} (HW fit)",
            line=dict(color=color, width=1, dash="dash"),
            opacity=0.4,
            hovertemplate=f"<b>{name} fitted</b><br>%{{y:.1f}}M SYP<extra></extra>",
        ))

    # Forecast lines (dashed diamond) bridged from last actual point
    for code, color in [("SYRIATEL", C["accent2"]), ("MTN", C["accent1"])]:
        if code not in forecast:
            continue
        fc = forecast[code]["forecast"]
        if fc is None or (hasattr(fc, "empty") and fc.empty):
            continue
        name = "Syriatel" if code == "SYRIATEL" else "MTN"
        bridge_x, bridge_y = [], []
        if not monthly_wide.empty and code in monthly_wide.columns:
            bridge_x.append(monthly_wide["label"].iloc[-1])
            bridge_y.append(float(monthly_wide[code].iloc[-1]))
        bridge_x += [d.strftime("%b %y") for d in fc.index]
        bridge_y += [float(v) / 1e6 for v in fc.values]

        traces.append(go.Scatter(
            x=bridge_x,
            y=bridge_y,
            mode="lines+markers",
            name=f"{name} (forecast)",
            line=dict(color=color, width=2, dash="dot"),
            marker=dict(size=7, color=color, symbol="diamond"),
            hovertemplate=f"<b>{name} forecast</b><br>%{{y:.1f}}M SYP<extra></extra>",
        ))

    layout_ov = dict(
        yaxis=dict(ticksuffix="M", gridcolor=C["border"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return _fig(traces, layout_ov, height=380)


# ---------------------------------------------------------------------------
# Tab layouts
# ---------------------------------------------------------------------------

def overview_tab(data: dict) -> html.Div:
    company_df   = data["company"]
    monthly_wide = data["monthly_wide"]

    total_rev_m = data["total_rev_syp"] / 1e6
    avg_order_k = data["avg_order_syp"] / 1e3

    kpi_row = [
        kpi_card("Total Revenue",   "إجمالي الإيرادات",   f"{total_rev_m:.1f}M SYP", "💰", C["gold"],    0.05),
        kpi_card("Total Orders",    "إجمالي الطلبات",     f"{data['total_orders']:,}", "📦", C["accent1"], 0.10),
        kpi_card("Customers",       "العملاء",            f"{data['total_customers']:,}", "👥", C["accent3"], 0.15),
        kpi_card("Cities Served",   "المدن المخدّمة",     str(data["cities_served"]),  "🏙️", C["accent5"], 0.20),
        kpi_card("Avg Order (SYP)", "متوسط الطلب",        f"{avg_order_k:.0f}K",       "📈", C["accent2"], 0.25),
        kpi_card("QoQ Growth",      "النمو الفصلي",       f"{data['qoq_growth']:+.1f}%", "🚀", C["accent3"], 0.30),
    ]

    # Market share legend
    share_legend = html.Div([
        legend_item(COMPANY_COLORS.get(row["company_code"], C["gold"]),
                    f"{row['company_name_en']} ({float(row['share_pct']):.1f}%)")
        for _, row in company_df.iterrows()
    ], style={"display": "flex", "justifyContent": "center", "gap": 24, "marginTop": 8})

    arch_nodes = [
        {"label": "Syriatel OLTP", "sub": "PostgreSQL :5433", "icon": "🗄️", "color": C["accent2"]},
        {"label": "MTN OLTP",      "sub": "PostgreSQL :5434", "icon": "🗄️", "color": C["accent1"]},
        {"label": "Python ETL",    "sub": "9 Divergences Resolved", "icon": "⚙️", "color": C["accent3"]},
        {"label": "Star Schema DW","sub": "PostgreSQL :5432", "icon": "⭐", "color": C["gold"]},
        {"label": "Analytics + Mining", "sub": "6 Queries · RFM · HW", "icon": "📊", "color": C["accent5"]},
    ]

    return html.Div([
        section_title(
            "Executive Dashboard", "لوحة المعلومات التنفيذية",
            "Unified view across Syriatel & MTN Syria — live warehouse data",
        ),
        html.Div(kpi_row, className="kpi-grid"),

        html.Div([
            # Market share donut
            chart_card([
                *chart_header("Market Share", "الحصة السوقية"),
                dcc.Graph(figure=company_share_pie(company_df), config={"displayModeBar": False, "responsive": True}, responsive=True),
                share_legend,
            ], {"flex": "1", "minWidth": 280}),

            # Monthly area trend
            chart_card([
                *chart_header("Monthly Revenue Trend", "الاتجاه الشهري للإيرادات"),
                dcc.Graph(figure=monthly_area_chart(monthly_wide), config={"displayModeBar": False, "responsive": True}, responsive=True),
            ], {"flex": "2", "minWidth": 380}),
        ], style={"display": "flex", "gap": 24, "marginBottom": 32, "flexWrap": "wrap"}),

        # Architecture banner
        chart_card([
            html.Div("System Architecture", className="chart-title-en mb-16"),
            html.Div([
                html.Div([
                    html.Div(n["icon"], style={"fontSize": 28, "marginBottom": 8}),
                    html.Div(n["label"], style={"fontSize": 13, "fontWeight": 600, "color": n["color"]}),
                    html.Div(n["sub"],   style={"fontSize": 11, "color": C["textMuted"], "marginTop": 4}),
                ], className="arch-node")
                for n in arch_nodes
            ], className="arch-grid"),
        ], {"background": "linear-gradient(135deg, #111827, #1a1f35)", "marginBottom": 0}),
    ])


def revenue_tab(data: dict) -> html.Div:
    company_df   = data["company"]
    comparison_df = data["comparison"]
    monthly_wide = data["monthly_wide"]
    products_df  = data["products"]

    # Company cards
    company_cards = []
    comp_map = {row["company_code"]: row.to_dict() for _, row in comparison_df.iterrows()} if not comparison_df.empty else {}

    for _, row in company_df.iterrows():
        code  = row["company_code"]
        color = COMPANY_COLORS.get(code, C["gold"])
        rev_m = float(row["total_sales_syp"]) / 1e6
        share = float(row["share_pct"])
        orders = int(row["order_count"])
        avg_k = float(row["avg_order_syp"]) / 1e3
        cmp = comp_map.get(code) or {}
        cust  = int(cmp.get("customer_count", 0))

        card = html.Div([
            html.Div([
                html.Div([
                    html.Div(row["company_name_en"],
                             style={"fontSize": 18, "fontWeight": 700, "color": color}),
                    html.Div(
                        "سيرياتل" if code == "SYRIATEL" else "إم تي إن سوريا",
                        className="arabic",
                        style={"fontSize": 14, "color": C["goldDim"]},
                    ),
                ]),
                html.Div(f"{share:.1f}%", style={
                    "background": f"{color}22", "color": color,
                    "padding": "4px 14px", "borderRadius": 20,
                    "fontSize": 13, "fontWeight": 600,
                }),
            ], className="flex-between mb-16"),

            html.Div([
                html.Div([
                    html.Div("Revenue", className="kpi-label-en"),
                    html.Div(f"{rev_m:.1f}M", style={"fontSize": 22, "fontWeight": 700, "color": C["text"]}),
                    html.Div("SYP", className="text-muted", style={"fontSize": 11}),
                ]),
                html.Div([
                    html.Div("Orders", className="kpi-label-en"),
                    html.Div(f"{orders:,}", style={"fontSize": 22, "fontWeight": 700, "color": C["text"]}),
                ]),
                html.Div([
                    html.Div("Avg Order", className="kpi-label-en"),
                    html.Div(f"{avg_k:.0f}K", style={"fontSize": 22, "fontWeight": 700, "color": C["text"]}),
                    html.Div("SYP", className="text-muted", style={"fontSize": 11}),
                ]),
                html.Div([
                    html.Div("Customers", className="kpi-label-en"),
                    html.Div(f"{cust:,}", style={"fontSize": 22, "fontWeight": 700, "color": C["text"]}),
                ]),
            ], style={"display": "grid", "gridTemplateColumns": "repeat(4, 1fr)", "gap": 16}),
        ], style={
            "background": C["card"], "border": f"1px solid {C['border']}",
            "borderLeft": f"4px solid {color}", "borderRadius": 16,
            "padding": 24, "flex": 1, "minWidth": 280,
        })
        company_cards.append(card)

    # Product category legend
    cat_legend = html.Div([
        legend_item(C["accent1"], "INTERNET"),
        legend_item(C["accent3"], "VOICE"),
        legend_item(C["accent2"], "BUNDLE"),
    ], style={"display": "flex", "justifyContent": "center", "gap": 24, "marginTop": 12})

    return html.Div([
        section_title(
            "Revenue Analysis", "تحليل الإيرادات",
            "Total sales per company, monthly trends, and product category breakdown",
        ),
        html.Div(company_cards,
                 style={"display": "flex", "gap": 24, "marginBottom": 32, "flexWrap": "wrap"}),

        chart_card([
            *chart_header("Monthly Revenue — Operator Comparison",
                          "مقارنة الإيرادات الشهرية بين المشغلين"),
            dcc.Graph(figure=monthly_bar_chart(monthly_wide), config={"displayModeBar": False, "responsive": True}, responsive=True),
        ], {"marginBottom": 0}),

        html.Div(style={"height": 24}),

        chart_card([
            *chart_header("Product Catalog — Average Order Value by Product",
                          "كتالوج المنتجات — متوسط قيمة الطلب لكل منتج"),
            dcc.Graph(figure=product_bar_chart(products_df), config={"displayModeBar": False, "responsive": True}, responsive=True),
            cat_legend,
        ], {"marginBottom": 0}),
    ])


def geo_tab(data: dict) -> html.Div:
    city_df = data["city"]
    max_rev = float(city_df["total_m"].max()) if not city_df.empty else 1

    city_cards = []
    for _, row in city_df.head(8).iterrows():
        syr_pct = float(row["syriatel_m"]) / float(row["total_m"]) * 100 if row["total_m"] else 50
        bar_pct = float(row["total_m"]) / max_rev * 100

        card = html.Div([
            html.Div([
                html.Div([
                    html.Div(row["city"], style={"fontSize": 15, "fontWeight": 600, "color": C["text"]}),
                    html.Div(row.get("city_ar", ""), className="arabic",
                             style={"fontSize": 13, "color": C["goldDim"]}),
                ]),
                html.Div(f"{float(row['total_m']):.1f}M",
                         style={"fontSize": 18, "fontWeight": 700, "color": C["gold"]}),
            ], className="flex-between mb-8"),

            # Revenue bar
            html.Div([
                html.Div(style={
                    "height": "100%", "borderRadius": 3,
                    "background": f"linear-gradient(90deg, {C['accent2']} {syr_pct:.0f}%, {C['accent1']} {syr_pct:.0f}%)",
                    "width": f"{bar_pct:.1f}%", "transition": "width 1s ease",
                })
            ], className="city-bar-bg"),

            html.Div([
                html.Span(f"🟡 Syriatel: {float(row['syriatel_m']):.1f}M",
                          style={"fontSize": 11, "color": C["textMuted"]}),
                html.Span(f"🔵 MTN: {float(row['mtn_m']):.1f}M",
                          style={"fontSize": 11, "color": C["textMuted"]}),
                html.Span(f"👥 {int(row['unique_customers'])}",
                          style={"fontSize": 11, "color": C["textMuted"]}),
            ], className="flex-between"),
        ], className="city-card")
        city_cards.append(card)

    return html.Div([
        section_title(
            "Geographic Revenue Distribution", "التوزيع الجغرافي للإيرادات",
            "Revenue by Syrian governorate — operator split across all cities",
        ),
        chart_card([
            html.Div("Revenue by City — Stacked by Operator",
                     className="chart-title-en mb-16"),
            dcc.Graph(figure=city_revenue_bar(city_df), config={"displayModeBar": False, "responsive": True}, responsive=True),
        ], {"marginBottom": 24}),

        html.Div(city_cards, className="city-grid"),
    ])


def customers_tab(data: dict) -> html.Div:
    rfm_summary  = data["rfm_summary"]
    at_risk      = data["at_risk_count"]
    champ_loyal  = data["champ_loyal_count"]
    total_cust   = data["total_customers"]

    # Segment cards
    seg_cards = []
    seg_order = ["Champions", "Loyal", "At Risk", "New", "Lost", "Other"]
    for i, seg in enumerate(seg_order):
        row = rfm_summary[rfm_summary["segment"] == seg]
        if row.empty:
            continue
        row = row.iloc[0]
        seg_cards.append(html.Div([
            html.Div(f"{int(row['count']):,}",
                     className="segment-count",
                     style={"color": row["color"]}),
            html.Div(seg, className="segment-name-en"),
            html.Div(row["segment_ar"], className="segment-name-ar arabic"),
            html.Div(f"{float(row['pct']):.1f}% of base", className="segment-pct"),
        ], className="segment-card",
           style={"borderTop": f"3px solid {row['color']}", "animationDelay": f"{i*0.08}s"}))

    # RFM rules table rows
    rfm_rules = [
        ("Champions", "أبطال",        "R ≥ 4 AND F ≥ 4 AND M ≥ 4", "#F59E0B"),
        ("Loyal",     "مخلصون",       "R ≥ 3 AND F ≥ 3",            "#10B981"),
        ("At Risk",   "معرضون للخطر", "R ≤ 2 AND F ≥ 3",            "#EF4444"),
        ("New",       "جدد",          "R ≥ 4 AND F = 1",             "#06B6D4"),
        ("Lost",      "مفقودون",      "R = 1 AND F ≤ 2",             "#8B5CF6"),
        ("Other",     "أخرى",         "Everything else",             "#6B7280"),
    ]
    table_rows = []
    for seg, ar, rule, clr in rfm_rules:
        row = rfm_summary[rfm_summary["segment"] == seg]
        count = int(row["count"].iloc[0]) if not row.empty else 0
        pct   = float(row["pct"].iloc[0])  if not row.empty else 0.0
        table_rows.append(html.Tr([
            html.Td(seg,   style={"color": clr, "fontWeight": 600, "padding": "10px 14px"}),
            html.Td(ar,    className="arabic", style={"color": C["goldDim"], "padding": "10px 14px"}),
            html.Td(rule,  className="mono",   style={"color": C["textDim"], "fontSize": 12, "padding": "10px 14px"}),
            html.Td(f"{count:,}", style={"fontWeight": 600, "color": C["text"], "padding": "10px 14px"}),
            html.Td(f"{pct:.1f}%", style={"color": C["textDim"], "padding": "10px 14px"}),
        ], style={"borderBottom": f"1px solid {C['border']}"}))

    at_risk_pct = at_risk / total_cust * 100 if total_cust else 0
    cl_pct      = champ_loyal / total_cust * 100 if total_cust else 0

    return html.Div([
        section_title(
            "Customer Segmentation (RFM)", "تقسيم العملاء (RFM)",
            "Recency × Frequency × Monetary quintile scoring across unified customers",
        ),
        html.Div(seg_cards, className="segment-grid"),

        html.Div([
            # Pie chart
            chart_card([
                html.Div("Segment Distribution", className="chart-title-en mb-16"),
                dcc.Graph(figure=rfm_pie_chart(rfm_summary), config={"displayModeBar": False, "responsive": True}, responsive=True),
                html.Div([
                    legend_item(r["color"], f"{r['segment']} ({float(r['pct']):.1f}%)")
                    for _, r in rfm_summary.iterrows()
                ], style={"display": "flex", "flexWrap": "wrap", "gap": 12, "marginTop": 12}),
            ], {"flex": 1, "minWidth": 280}),

            # Alert cards
            html.Div([
                html.Div([
                    html.Div([
                        html.Span("⚠️", style={"fontSize": 22}),
                        html.Span("At Risk Alert",
                                  style={"fontSize": 16, "fontWeight": 700, "color": C["accent4"], "marginLeft": 10}),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": 12}),
                    html.Div([
                        html.Span(f"{at_risk:,}", style={"fontSize": 36, "fontWeight": 700, "color": C["text"]}),
                        html.Span(" customers", style={"fontSize": 15, "color": C["textDim"]}),
                    ]),
                    html.P(
                        f"{at_risk_pct:.1f}% of the customer base were regular buyers who have become inactive. "
                        "This is the most actionable cohort for retention campaigns.",
                        style={"fontSize": 13, "color": C["textDim"], "lineHeight": 1.6, "marginTop": 8},
                    ),
                    html.P(
                        f"{at_risk:,} عميلاً ({at_risk_pct:.1f}%) كانوا مشترين منتظمين وأصبحوا غير نشطين — "
                        "الشريحة الأكثر أهمية لحملات الاحتفاظ",
                        className="arabic",
                        style={"fontSize": 12, "color": C["goldDim"], "lineHeight": 1.8, "marginTop": 8},
                    ),
                ], className="alert-card-red"),

                html.Div([
                    html.Div([
                        html.Span("🏆", style={"fontSize": 22}),
                        html.Span("Champions + Loyal",
                                  style={"fontSize": 16, "fontWeight": 700, "color": C["accent3"], "marginLeft": 10}),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": 10}),
                    html.Div([
                        html.Span(f"{champ_loyal:,}", style={"fontSize": 36, "fontWeight": 700, "color": C["text"]}),
                        html.Span(" customers", style={"fontSize": 15, "color": C["textDim"]}),
                    ]),
                    html.P(
                        f"{cl_pct:.1f}% of the base — high-value, high-frequency buyers driving the majority of revenue.",
                        style={"fontSize": 13, "color": C["textDim"], "marginTop": 8},
                    ),
                ], className="alert-card-green"),
            ], style={"flex": 1, "minWidth": 280, "display": "flex", "flexDirection": "column", "justifyContent": "center"}),
        ], style={"display": "flex", "gap": 24, "marginBottom": 32, "flexWrap": "wrap"}),

        # RFM rules table
        chart_card([
            html.Div("RFM Segmentation Rules", className="chart-title-en mb-16"),
            html.Div([
                html.Table([
                    html.Thead(html.Tr([
                        html.Th(h, style={"padding": "10px 14px", "textAlign": "left",
                                          "color": C["textMuted"], "fontSize": 11,
                                          "textTransform": "uppercase", "fontWeight": 500,
                                          "borderBottom": f"1px solid {C['border']}"})
                        for h in ["Segment", "الشريحة", "Rule (R / F / M quintiles)", "Count", "%"]
                    ])),
                    html.Tbody(table_rows),
                ], className="dw-table dw-table-rfm"),
            ], style={"overflowX": "auto"}),
        ]),
    ])


def forecast_tab(data: dict) -> html.Div:
    monthly_wide = data["monthly_wide"]
    forecast     = data["forecast"]

    syr = forecast.get("SYRIATEL", {})
    mtn = forecast.get("MTN", {})

    syr_rmse = syr.get("rmse", 7.38e6)
    syr_mape = syr.get("mape", 12.98)
    mtn_rmse = mtn.get("rmse", 7.82e6)
    mtn_mape = mtn.get("mape", 12.91)

    syr_fc = syr.get("forecast", None)
    mtn_fc = mtn.get("forecast", None)

    stat_cards = [
        ("Syriatel RMSE",  f"{syr_rmse/1e6:.2f}M SYP", C["accent2"]),
        ("Syriatel MAPE",  f"{syr_mape:.1f}%",          C["accent2"]),
        ("MTN RMSE",       f"{mtn_rmse/1e6:.2f}M SYP",  C["accent1"]),
        ("MTN MAPE",       f"{mtn_mape:.1f}%",           C["accent1"]),
        ("Trend (Both)",   "~+1.5M/month",               C["accent3"]),
        ("Forecast Horizon", "3 months",                 C["accent5"]),
    ]

    stat_divs = [
        html.Div([
            html.Div(label, style={"fontSize": 11, "color": C["textMuted"],
                                   "textTransform": "uppercase", "letterSpacing": "0.05em"}),
            html.Div(val, style={"fontSize": 18, "fontWeight": 700, "color": C["text"], "marginTop": 6}),
        ], className="stat-card", style={"borderLeftColor": color})
        for label, val, color in stat_cards
    ]

    # Forecast values table
    fc_rows = []
    months = ["May 2026", "Jun 2026", "Jul 2026"]
    syr_vals = list(syr_fc.values) if syr_fc is not None and not syr_fc.empty else [64.7e6, 66.2e6, 67.6e6]
    mtn_vals = list(mtn_fc.values) if mtn_fc is not None and not mtn_fc.empty else [64.6e6, 65.9e6, 67.3e6]
    if syr_fc is not None and not syr_fc.empty:
        months = [d.strftime("%b %Y") for d in syr_fc.index]

    for month, sv, mv in zip(months, syr_vals, mtn_vals):
        sv_m, mv_m = float(sv) / 1e6, float(mv) / 1e6
        fc_rows.append(html.Tr([
            html.Td(month,                   style={"padding": "10px", "color": C["text"], "fontWeight": 500}),
            html.Td(f"{sv_m:.1f}M",          style={"padding": "10px", "color": C["accent2"]}),
            html.Td(f"{mv_m:.1f}M",          style={"padding": "10px", "color": C["accent1"]}),
            html.Td(f"{sv_m + mv_m:.1f}M",   style={"padding": "10px", "color": C["gold"], "fontWeight": 600}),
        ], style={"borderBottom": f"1px solid {C['border']}"}))

    methodology = [
        ("Model",      "Holt-Winters Exponential Smoothing"),
        ("Trend",      "Additive (~+1.5M SYP/month)"),
        ("Seasonal",   "None (12 months insufficient)"),
        ("Holdout",    "Last month excluded (partial)"),
        ("Confidence", "80% bands"),
        ("Horizon",    "3 months forward"),
    ]

    return html.Div([
        section_title(
            "Forecast & Data Mining", "التنبؤ وتنقيب البيانات",
            "Holt-Winters Exponential Smoothing — 3-month forecast with additive trend",
        ),
        html.Div(stat_divs, className="forecast-stats-grid"),

        chart_card([
            *chart_header(
                "Revenue Forecast — Actual vs Holt-Winters Prediction",
                "التنبؤ بالإيرادات — الفعلي مقابل نموذج هولت-وينترز",
            ),
            dcc.Graph(figure=forecast_chart(monthly_wide, forecast), config={"displayModeBar": False, "responsive": True}, responsive=True),
        ], {"marginBottom": 24}),

        html.Div([
            # Methodology
            chart_card([
                html.Div("Methodology", style={"fontSize": 14, "fontWeight": 700, "color": C["gold"], "marginBottom": 16}),
                *[html.Div([
                    html.Span(k, style={"color": C["textMuted"], "fontSize": 13}),
                    html.Span(v, style={"color": C["text"], "fontSize": 13, "fontWeight": 500}),
                ], style={"display": "flex", "justifyContent": "space-between",
                           "padding": "8px 0", "borderBottom": f"1px solid {C['border']}" if i < len(methodology)-1 else "none"})
                  for i, (k, v) in enumerate(methodology)],
            ], {"flex": 1, "minWidth": 260}),

            # Forecast values
            chart_card([
                html.Div("Forecast Values (M SYP)",
                         style={"fontSize": 14, "fontWeight": 700, "color": C["gold"], "marginBottom": 16}),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th(h, style={"padding": "8px 10px", "textAlign": "left",
                                          "color": C["textMuted"], "fontSize": 11,
                                          "textTransform": "uppercase",
                                          "borderBottom": f"1px solid {C['border']}"})
                        for h in ["Month", "Syriatel", "MTN", "Combined"]
                    ])),
                    html.Tbody(fc_rows),
                ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": 13}),
            ], {"flex": 1, "minWidth": 260}),
        ], style={"display": "flex", "gap": 24, "flexWrap": "wrap"}),
    ])


def recommendations_tab(_data: dict) -> html.Div:
    recs = [
        {
            "num": 1, "priority": "HIGH", "color": C["accent4"],
            "title":    "Early-Warning System for At-Risk Customers",
            "title_ar": "نظام إنذار مبكر للعملاء المعرضين للخطر",
            "body": (
                "365 customers (18.2%) were regular buyers and have stopped. Deploy automated alerts "
                "when a customer's R-score crosses a threshold to trigger targeted retention campaigns."
            ),
        },
        {
            "num": 2, "priority": "HIGH", "color": C["accent2"],
            "title":    "Monitor Revenue Concentration in Top 10%",
            "title_ar": "مراقبة تركّز الإيرادات في أعلى 10%",
            "body": (
                "Run quarterly checks on top-10% revenue share. If it exceeds 50%, review pricing "
                "and ramp acquisition for mid-tier segments to reduce dependency."
            ),
        },
        {
            "num": 3, "priority": "MEDIUM", "color": C["accent1"],
            "title":    "Geographic Disparity Analysis & Rural Investment",
            "title_ar": "تحليل التفاوت الجغرافي والاستثمار الريفي",
            "body": (
                "Low-revenue cities need root-cause analysis: coverage gaps vs. purchasing power vs. "
                "population density. Targeted infrastructure investment decisions should follow."
            ),
        },
        {
            "num": 4, "priority": "MEDIUM", "color": C["accent5"],
            "title":    "Audit Syriatel's Stored-Total Computation",
            "title_ar": "تدقيق حساب المبلغ المخزّن في سيرياتل",
            "body": (
                "Inconsistencies between total_price and qty × price indicate an application-layer bug. "
                "Recommend dropping the stored column in favour of computed-at-query or a CHECK CONSTRAINT."
            ),
        },
        {
            "num": 5, "priority": "LOW", "color": C["accent3"],
            "title":    "Expand Forecasting After 24 Months of Data",
            "title_ar": "توسيع نماذج التنبؤ بعد 24 شهراً من البيانات",
            "body": (
                "Current 12-month Holt-Winters is sound but limited. SARIMA becomes viable at 24 months, "
                "enabling seasonal decomposition and more reliable strategic planning."
            ),
        },
        {
            "num": 6, "priority": "HIGH", "color": C["accent4"],
            "title":    "Issue a Unified Data-Format Standard",
            "title_ar": "إصدار معيار موحّد لتنسيق البيانات",
            "body": (
                "Mandate E.164 phones, a canonical city dictionary, and UPPER product categories across "
                "all operators. This collapses future ETL complexity dramatically."
            ),
        },
        {
            "num": 7, "priority": "MEDIUM", "color": C["accent1"],
            "title":    "Promote Dashboard to Production Monitoring",
            "title_ar": "ترقية لوحة المعلومات إلى أداة مراقبة إنتاجية",
            "body": (
                "Provide read-only access for Ministry analysts, plus automated alerts on KPI threshold "
                "breaches for proactive decision-making."
            ),
        },
    ]

    priority_bg = {"HIGH": C["accent4"], "MEDIUM": C["accent1"], "LOW": C["accent3"]}

    rec_cards = []
    for i, r in enumerate(recs):
        pbg = priority_bg.get(r["priority"], C["gold"])
        rec_cards.append(html.Div([
            html.Div([
                html.Span(str(r["num"]), style={
                    "background": f"{r['color']}22", "color": r["color"],
                    "fontWeight": 700, "fontSize": 13,
                    "width": 30, "height": 30, "borderRadius": 8,
                    "display": "inline-flex", "alignItems": "center",
                    "justifyContent": "center", "marginRight": 12,
                    "flexShrink": 0,
                }),
                html.Span(r["title"],
                          style={"fontSize": 16, "fontWeight": 700, "color": C["text"]}),
                html.Span(r["priority"], style={
                    "background": f"{pbg}20", "color": pbg,
                    "padding": "2px 10px", "borderRadius": 10,
                    "fontSize": 10, "fontWeight": 700, "letterSpacing": "0.05em",
                    "marginLeft": 10,
                }),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": 8, "flexWrap": "wrap"}),
            html.Div(r["title_ar"], className="arabic",
                     style={"fontSize": 13, "color": C["goldDim"], "marginBottom": 10}),
            html.P(r["body"], style={"fontSize": 13, "color": C["textDim"],
                                     "lineHeight": 1.7, "margin": 0}),
        ], className="rec-card",
           style={"borderLeftColor": r["color"], "animationDelay": f"{i*0.06}s"}))

    # ETL divergence table
    divergences = [
        ("Table naming",   "customers / products / orders", "clients / items / transactions", "Conformed dim_* / fact_*"),
        ("Primary key",    "SERIAL integer",                 "UUID",                            "Surrogate *_sk keys"),
        ("City storage",   "Arabic (دمشق)",                  "English (Damascus)",               "Canonical English via CSV"),
        ("Phone format",   "E.164 (+963…)",                  "National (09…)",                   "Normalized to +963…"),
        ("Price type",     "INTEGER (SYP)",                  "NUMERIC(12,2)",                    "NUMERIC(14,2)"),
        ("Order total",    "Stored column",                  "Not stored",                       "Computed + validated"),
        ("Date storage",   "Single TIMESTAMP",               "Separate DATE + TIME",             "date_sk (YYYYMMDD)"),
        ("Category case",  "Title Case",                     "UPPER",                            "Normalized to UPPER"),
        ("Product names",  "Arabic (باقة 5GB)",              "English (5GB Bundle)",             "Canonical English"),
    ]

    div_rows = [
        html.Tr([
            html.Td(str(i+1), style={"padding": "10px 12px", "color": C["gold"], "fontWeight": 700}),
            html.Td(d,        style={"padding": "10px 12px", "color": C["text"], "fontWeight": 500}),
            html.Td(s,        className="mono", style={"padding": "10px 12px", "color": C["accent2"], "fontSize": 11}),
            html.Td(m,        className="mono", style={"padding": "10px 12px", "color": C["accent1"], "fontSize": 11}),
            html.Td(r,        style={"padding": "10px 12px", "color": C["accent3"], "fontSize": 11}),
        ], style={"borderBottom": f"1px solid {C['border']}"})
        for i, (d, s, m, r) in enumerate(divergences)
    ]

    return html.Div([
        section_title(
            "Ministry Recommendations", "توصيات الوزارة",
            "Actionable insights derived from the unified warehouse analysis",
        ),
        html.Div(rec_cards, style={"display": "flex", "flexDirection": "column", "gap": 16}),

        html.Div(style={"height": 40}),
        section_title(
            "ETL Divergence Resolution", "حل تباينات ETL",
            "9 structural differences between Syriatel and MTN resolved by the pipeline",
        ),
        chart_card([
            html.Div([
                html.Table([
                    html.Thead(html.Tr([
                        html.Th(h, style={"padding": "10px 12px", "textAlign": "left",
                                          "color": C["gold"], "fontWeight": 600,
                                          "fontSize": 11, "textTransform": "uppercase",
                                          "borderBottom": f"2px solid {C['gold']}44"})
                        for h in ["#", "Dimension", "Syriatel", "MTN Syria", "Resolution"]
                    ])),
                    html.Tbody(div_rows),
                ], className="dw-table"),
            ], style={"overflowX": "auto"}),
        ]),
    ])
