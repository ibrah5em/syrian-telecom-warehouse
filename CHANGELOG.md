# Changelog

All notable changes to the Syrian Telecom Data Warehouse project are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — feature/dash-dashboard

### Added

#### Plotly Dash Analytics Dashboard (`dashboard/`)

- **`dashboard/app.py`** — Dash application entry point.
  - Six-tab navigation: Overview, Revenue Analysis, Geographic, Customer Segments, Forecast & Mining, Recommendations.
  - Sticky bilingual header (English + Arabic) with Ministry of Communications branding.
  - Live status indicator; footer dynamically shows order / customer / city / product counts from the DW.
  - `render_tab` callback switches tab content without full-page reload.
  - Graceful error state when the warehouse is unreachable (displays connection URL for debugging).
  - Serves via Gunicorn in production (`server = app.server`).

- **`dashboard/data.py`** — Warehouse query layer and data transformation module.
  - Single `load_all_data()` call at startup; result cached in a module-level global — zero per-request DB hits.
  - Runs all six analytical SQL queries against `dw.*` tables using `psycopg2` + `pd.read_sql`.
  - `_Q_COMPANY_TOTALS` — revenue, order count, market share per operator.
  - `_Q_TOP_CUSTOMERS` — top 20 spenders with first/last order dates.
  - `_Q_CITY_SALES` — Syriatel vs MTN revenue cross-tab per city.
  - `_Q_MONTHLY_SALES` — monthly time series per operator.
  - `_Q_COMPANY_COMPARISON` — side-by-side KPIs (revenue, customers, AOV, cities, categories).
  - `_Q_KPI_INDICATORS` — composite ministerial KPIs: top-decile share, QoQ growth, grand total.
  - `_Q_PRODUCTS` — average order value per product/category from `dim_product ⋈ fact_sales`.
  - `_Q_RFM_RAW` — raw RFM values (recency in days, frequency, monetary) from the DW.
  - `_score_rfm()` — quintile scoring (1–5) via `pd.qcut` + rank tie-breaking, matching `rfm_segment.py`.
  - `_assign_segments()` — rule-based segment labelling (Champions / Loyal / At Risk / New / Lost / Other).
  - `_compute_forecast()` — Holt-Winters additive-trend model via `statsmodels`; fits per operator, computes in-sample RMSE and MAPE, forecasts 3 months ahead.
  - `_fallback_forecast()` — returns JSX reference values if `statsmodels` is unavailable.
  - `build_monthly_wide()` — pivots long monthly data to wide format (columns SYRIATEL / MTN) in millions SYP.
  - Arabic city name mapping (`CITY_ARABIC`) and company name mapping (`COMPANY_ARABIC`).

- **`dashboard/components.py`** — Plotly figure builders and Dash HTML component helpers.
  - Shared dark-theme Plotly layout factory (`_base_layout`) — `#111827` bg, `#1E293B` grid, `DM Sans` font.
  - `company_share_pie()` — donut chart (hole=0.6) showing operator market share.
  - `monthly_area_chart()` — filled area chart with per-operator gradient fills.
  - `monthly_bar_chart()` — grouped bar chart, month on x-axis, operators side by side.
  - `city_revenue_bar()` — stacked horizontal bar, sorted by total revenue descending.
  - `product_bar_chart()` — horizontal bar coloured by product category (INTERNET / VOICE / BUNDLE).
  - `rfm_pie_chart()` — full pie for six RFM segments with segment-specific colours.
  - `forecast_chart()` — combined line chart: actual (solid) + forecast (dashed diamond markers) with bridge point from last actual to first forecast.
  - `kpi_card()` — bilingual KPI card with background glow, icon, animated CSS entrance.
  - `section_title()` — bilingual section header with gold underline divider.
  - `chart_card()` — dark card wrapper for all charts.
  - Six tab layout functions: `overview_tab`, `revenue_tab`, `geo_tab`, `customers_tab`, `forecast_tab`, `recommendations_tab` — each accepts the pre-loaded `data` dict and returns a `dash.html.Div` subtree.

- **`dashboard/assets/style.css`** — Dark Ministry-grade theme.
  - Palette: background `#0A0E1A`, cards `#111827`, borders `#1E293B`, gold `#D4A843`, Syriatel amber `#F59E0B`, MTN blue `#3B82F6`.
  - Google Fonts: DM Sans (UI), Noto Kufi Arabic (Arabic labels), DM Mono (code/values).
  - Custom `dcc.Tabs` override via `.custom-tab` / `.custom-tab--selected` for gold underline nav.
  - CSS keyframe animations: `fadeSlideUp`, `pulse` (live dot), `gradientShift`.
  - Scrollbar theming, responsive grid breakpoints at 768px.
  - Utility classes: `.arabic`, `.mono`, `.text-gold`, `.text-syriatel`, `.text-mtn`, flex/gap/margin helpers.

- **`dashboard/requirements.txt`** — pinned dependency set: `dash==2.17.1`, `plotly==5.22.0`, `psycopg2-binary==2.9.9`, `pandas==2.2.2`, `numpy==1.26.4`, `statsmodels==0.14.2`, `python-dotenv==1.0.1`, `gunicorn==22.0.0`.

- **`dashboard/Dockerfile`** — `python:3.11-slim` base; installs requirements, copies app, exposes port 8050; CMD runs `python app.py`.

#### Infrastructure Changes

- **`docker-compose.yml`** — added `dashboard` service:
  - Builds from `./dashboard`.
  - Exposes port `8050`.
  - `DATABASE_URL` wired to the `dw` service using compose variable substitution (`${DW_USER:-dw}`, `${DW_PASSWORD:-dw}`, `${DW_DB:-telecom_dw}`).
  - `depends_on: dw: condition: service_healthy` — waits for the DW to pass its health check before starting.
  - Joined to `telecom_net` bridge network.

- **`Makefile`** — two new targets:
  - `make dash-build` — builds the dashboard image and starts the container; prints `http://localhost:8050`.
  - `make dash-logs` — tails `telecom_dashboard` container logs.

---

## [1.0.0] — Initial Release (main)

### Added

- **Three-tier architecture**: Syriatel OLTP (port 5433), MTN OLTP (port 5434), star-schema DW (port 5435).
- **ETL pipeline** (`etl/`) resolving 9 systematic schema divergences between the two operators.
- **Star schema** (`dw/schema.sql`): `fact_sales`, `dim_customer`, `dim_product`, `dim_date`, `dim_company`, `etl_runs`, `etl_errors`.
- **pg_cron** weekly Sunday 02:00 UTC schedule + LISTEN/NOTIFY decoupling via `etl/listener.py`.
- **6 analytical SQL queries** (`analytics/0*.sql`) answering Ministry-of-Communications questions.
- **Data mining**: RFM quintile segmentation (`analytics/mining/rfm_segment.py`) and Holt-Winters 3-month forecast (`analytics/mining/forecast.py`).
- **Metabase** dashboard at port 3000 with automated setup script.
- **Reference data**: `data/syrian_cities.csv` (Arabic ↔ English, 17 cities), `data/product_catalog.csv` (15 products, bilingual names + categories).
- **Seed scripts**, divergence verification, Docker Compose orchestration for all 5 services.
- **CI workflow** (`.github/workflows/ci.yml`) — runs ETL twice to verify idempotency.
