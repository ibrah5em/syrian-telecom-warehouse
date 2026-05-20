# Telecom DW — Plotly Dash Dashboard

Presentation-quality analytics dashboard for the Syrian Telecom Data Warehouse.  
Bilingual (Arabic / English) · Dark theme · Live warehouse data · Ministry of Communications grade.

---

## Quick Start

### Via Docker Compose (recommended)

```bash
# From the project root — builds the image and starts on port 8050
make dash-build

# Open the dashboard
open http://localhost:8050

# Tail logs
make dash-logs
```

The service waits for the `dw` container to report healthy before starting.

### Locally (for development)

```bash
cd dashboard
pip install -r requirements.txt

# Point at the DW — use port 5435 which is forwarded to your host
DATABASE_URL=postgresql://dw:dw@localhost:5435/telecom_dw python app.py
```

The app reloads automatically when `debug=true` (`DEBUG=true` env var).

---

## Architecture

```
dashboard/
├── app.py            # Dash entry point — layout, tab callback, footer
├── data.py           # All SQL queries + RFM scoring + Holt-Winters forecast
├── components.py     # Plotly figure builders + Dash HTML component helpers
├── assets/
│   └── style.css     # Dark theme, Arabic fonts, animations, tab nav overrides
├── requirements.txt
├── Dockerfile
└── README.md
```

### Data flow

```
PostgreSQL DW (dw schema)
        │
        ▼
data.load_all_data()          ← runs once at startup, cached in memory
        │
        ├── _qdf(SQL)         ← pd.read_sql via psycopg2
        ├── _score_rfm()      ← quintile scoring (matches rfm_segment.py)
        ├── _assign_segments()← Champions / Loyal / At Risk / New / Lost / Other
        └── _compute_forecast()← Holt-Winters via statsmodels
                │
                ▼
        components.*_tab(data)← builds Plotly figures + Dash HTML
                │
                ▼
        app.render_tab()      ← dcc.Tabs callback, returns layout
```

---

## Tabs

| Tab | Content | Key SQL |
|-----|---------|---------|
| **Overview** | 6 KPI cards · market share donut · monthly area chart · architecture banner | Q1, Q6 |
| **Revenue Analysis** | Operator cards · monthly grouped bar · product catalog bar | Q1, Q4, Q5, products |
| **Geographic** | City stacked horizontal bar · top-8 city cards with split bars | Q3 |
| **Customer Segments** | RFM segment cards · pie chart · at-risk / champions alerts · rules table | RFM |
| **Forecast & Mining** | Model stats · actual + forecast line chart · methodology · values table | Q4 + HW |
| **Recommendations** | 7 Ministry recommendations · ETL divergence resolution table | — |

---

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://dw:dw@dw:5432/telecom_dw` | Full DW connection string |
| `PORT` | `8050` | Dash server port |
| `DEBUG` | `false` | Enable Dash hot-reload |

In Docker Compose the variables are injected from the root `.env` file via variable substitution (`${DW_USER:-dw}` etc.).

---

## Design System

### Colour Palette

| Token | Hex | Usage |
|-------|-----|-------|
| Background | `#0A0E1A` | Page background |
| Card | `#111827` | Chart and KPI cards |
| Border | `#1E293B` | Card borders, grid lines |
| Gold | `#D4A843` | Accent, section dividers, tab indicator |
| Gold Dim | `#8B7235` | Arabic subtitle labels |
| Syriatel | `#F59E0B` | Syriatel data series |
| MTN | `#3B82F6` | MTN data series |
| Green | `#10B981` | Positive indicators, Champions/Loyal |
| Red | `#EF4444` | At-risk alerts |
| Purple | `#8B5CF6` | Lost segment, forecast horizon |

### Fonts

- **DM Sans** — primary UI, KPI values, section titles
- **Noto Kufi Arabic** — all Arabic labels (`direction: rtl`)
- **DM Mono** — code values, RFM rules, divergence table

Fonts are loaded from Google Fonts via the CSS `@import`.

---

## Forecast Methodology

The Forecast tab runs a live Holt-Winters Exponential Smoothing model:

- **Model**: `ExponentialSmoothing(trend='add', seasonal=None)`
- **Why no seasonality**: 12 months of data is insufficient to identify a 12-period seasonal cycle (statsmodels requires ≥ 2 full cycles).
- **Holdout**: the last partial month is dropped before fitting to avoid downward bias.
- **Horizon**: 3 months forward.
- **Fallback**: if `statsmodels` is not installed or data is too sparse (< 3 months), hardcoded reference values from the JSX reference design are used.
- **Metrics reported**: in-sample RMSE (millions SYP) and MAPE (%).

---

## RFM Segmentation

Mirrors `analytics/mining/rfm_segment.py` exactly:

| Score | Dimension | Rule |
|-------|-----------|------|
| R 1–5 | Recency | Fewer days since last order → higher score |
| F 1–5 | Frequency | More orders → higher score |
| M 1–5 | Monetary | Higher total spend → higher score |

Segments (first-match priority):

| Segment | شريحة | Rule |
|---------|-------|------|
| Champions | أبطال | R ≥ 4 AND F ≥ 4 AND M ≥ 4 |
| Loyal | مخلصون | R ≥ 3 AND F ≥ 3 |
| At Risk | معرضون للخطر | R ≤ 2 AND F ≥ 3 |
| New | جدد | R ≥ 4 AND F = 1 |
| Lost | مفقودون | R = 1 AND F ≤ 2 |
| Other | أخرى | Everything else |

---

## Adding to an Existing Compose Stack

The dashboard service is already declared in `docker-compose.yml`. To start only the dashboard alongside the DW:

```bash
docker compose up -d dw dashboard
```

---

## Production Notes

- The Dash `server` object is exposed as a WSGI app (`server = app.server`). Swap the CMD to Gunicorn for multi-worker production:
  ```dockerfile
  CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "2", "app:server"]
  ```
- Data is loaded once at process startup. To refresh after an ETL run, restart the container or add a manual reload endpoint.
- For Ministry deployment, add Nginx in front to handle TLS termination and `/` path prefix.
