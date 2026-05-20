"""
Monthly sales forecast (Holt-Winters) for the telecom-dw project.

Run from project root:
    python -m analytics.mining.forecast

Queries monthly total_amount_syp per operator, fits an additive-trend
Holt-Winters model (no seasonal component — 12 months is insufficient
to identify a 12-period seasonal cycle), and forecasts 3 months ahead.

Outputs:
    docs/screenshots/forecast-syriatel.png
    docs/screenshots/forecast-mtn.png
    analytics/mining/output/forecast-syriatel.csv
    analytics/mining/output/forecast-mtn.csv
"""

import logging
import os
import pathlib
import sys
import warnings

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be set before pyplot import
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from dotenv import load_dotenv

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
except ImportError:
    print("ERROR: statsmodels is not installed. Run: pip install statsmodels", file=sys.stderr)
    sys.exit(1)

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg[binary] is not installed. Run: pip install psycopg[binary]", file=sys.stderr)
    sys.exit(1)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT_DIR = pathlib.Path(__file__).parent / "output"
SCREENSHOTS_DIR = PROJECT_ROOT / "docs" / "screenshots"

# Run date pinned per task requirement
RUN_DATE = "2026-05-15"

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------
def get_conn():
    return psycopg.connect(
        host=os.environ["DW_HOST"],
        port=int(os.environ.get("DW_PORT", 5435)),
        user=os.environ["DW_USER"],
        password=os.environ["DW_PASSWORD"],
        dbname=os.environ["DW_DB"],
    )


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------
MONTHLY_SALES_SQL = """
    SELECT
        d.year,
        d.month,
        co.company_code,
        co.company_name_en  AS company_name,
        SUM(f.total_amount_syp) AS sales_syp
    FROM fact_sales f
    JOIN dim_date    d  ON d.date_sk    = f.date_sk
    JOIN dim_company co ON co.company_sk = f.company_sk
    GROUP BY d.year, d.month, co.company_code, co.company_name_en
    ORDER BY co.company_code, d.year, d.month
"""


def load_monthly_data() -> pd.DataFrame:
    log.info("Connecting to DW at %s:%s", os.environ["DW_HOST"], os.environ.get("DW_PORT", 5435))
    # Use native cursor to avoid SQLAlchemy requirement with psycopg3
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(MONTHLY_SALES_SQL)
            rows = cur.fetchall()
            cols = [desc.name for desc in cur.description]
    df = pd.DataFrame(rows, columns=cols)
    # Ensure numeric types
    df["sales_syp"] = pd.to_numeric(df["sales_syp"])
    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    log.info("Loaded %d monthly rows from DW", len(df))
    return df


# ---------------------------------------------------------------------------
# Forecast per company
# ---------------------------------------------------------------------------
def build_series(df: pd.DataFrame, company_code: str) -> pd.Series:
    """Return a monthly time series for the given company, sorted by period."""
    sub = df[df["company_code"] == company_code].copy()
    # Build a proper DatetimeIndex using year+month (first day of month)
    sub["period"] = pd.to_datetime(
        sub["year"].astype(str) + "-" + sub["month"].astype(str).str.zfill(2) + "-01"
    )
    sub = sub.sort_values("period").set_index("period")["sales_syp"]
    # Drop the final partial month: the last calendar month in the DW
    # may be incomplete (seeded data runs mid-month). Drop it to avoid a
    # downward bias that would distort the trend.
    if len(sub) > 1 and sub.index[-1].month == pd.Timestamp(RUN_DATE).month:
        log.info("Dropping partial month %s for %s", sub.index[-1].strftime("%Y-%m"), company_code)
        sub = sub.iloc[:-1]
    return sub


def fit_forecast(series: pd.Series, company_code: str, n_forecast: int = 3):
    """
    Fit Holt-Winters with additive trend.

    Seasonal component is omitted because 12 months of data is insufficient
    to identify a 12-period seasonal cycle — statsmodels requires at least
    two full cycles (24 months) for a seasonal fit.
    """
    n = len(series)
    log.info("Fitting model for %s on %d monthly observations", company_code, n)

    model_params = dict(trend="add", seasonal=None, initialization_method="estimated")
    log.info("Model params: %s", model_params)

    model = ExponentialSmoothing(series.values.astype(float), **model_params)
    # ConvergenceWarning is expected on short series (12 pts): optimizer may find
    # alpha=0/beta=0 as optimal, which is a valid degenerate solution, not a failure.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = model.fit(optimized=True)

    log.info(
        "Fit complete — alpha=%.4f, beta=%.4f, SSE=%.2f",
        fit.params.get("smoothing_level", float("nan")),
        fit.params.get("smoothing_trend", float("nan")),
        fit.sse,
    )

    forecast_values = fit.forecast(n_forecast)

    # Build forecast index (continuing monthly from last observed period)
    last_period = series.index[-1]
    forecast_index = pd.date_range(
        start=last_period + pd.DateOffset(months=1),
        periods=n_forecast,
        freq="MS",
    )

    fitted_series = pd.Series(fit.fittedvalues, index=series.index)
    forecast_series = pd.Series(forecast_values, index=forecast_index)

    return fit, fitted_series, forecast_series


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def compute_metrics(actual: pd.Series, fitted: pd.Series) -> dict:
    """Compute in-sample RMSE and MAPE."""
    actual_v = actual.values.astype(float)
    fitted_v = fitted.values.astype(float)
    rmse = float(np.sqrt(np.mean((actual_v - fitted_v) ** 2)))
    # Guard against zero actuals in MAPE
    with np.errstate(divide="ignore", invalid="ignore"):
        ape = np.where(actual_v != 0, np.abs((actual_v - fitted_v) / actual_v), np.nan)
    mape = float(np.nanmean(ape) * 100)
    return {"rmse": rmse, "mape": mape}


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
def plot_forecast(
    actual: pd.Series,
    fitted: pd.Series,
    forecast: pd.Series,
    company_name: str,
    company_code: str,
    output_path: pathlib.Path,
    metrics: dict,
):
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(actual.index, actual.values / 1e6, marker="o", label="Actual", linewidth=2, color="#1f77b4")
    ax.plot(fitted.index, fitted.values / 1e6, linestyle="--", label="Fitted", linewidth=1.5, color="#ff7f0e")
    ax.plot(forecast.index, forecast.values / 1e6, marker="s", linestyle="-.", label="Forecast (+3 months)", linewidth=2, color="#2ca02c")

    # Shade forecast region
    ax.axvspan(forecast.index[0], forecast.index[-1], alpha=0.08, color="#2ca02c")

    ax.set_title(
        f"{company_name} — Monthly Sales Forecast\n"
        f"Holt-Winters (additive trend, no seasonality) | "
        f"Forecast generated {RUN_DATE}",
        fontsize=12,
    )
    ax.set_xlabel("Month")
    ax.set_ylabel("Sales (millions SYP)")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.autofmt_xdate(rotation=45)
    ax.grid(True, alpha=0.3)

    # Annotate metrics
    metrics_text = f"In-sample RMSE: {metrics['rmse']/1e6:.2f}M SYP\nIn-sample MAPE: {metrics['mape']:.1f}%"
    ax.text(
        0.02, 0.97, metrics_text,
        transform=ax.transAxes, verticalalignment="top",
        fontsize=9, bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.5),
    )

    # Annotate forecast values
    for idx, val in zip(forecast.index, forecast.values):
        ax.annotate(
            f"{val/1e6:.1f}M",
            (idx, val / 1e6),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=8,
            color="#2ca02c",
        )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved PNG to %s", output_path)


# ---------------------------------------------------------------------------
# Sanity check
# ---------------------------------------------------------------------------
def sanity_check(actual: pd.Series, forecast: pd.Series, company_code: str):
    hist_max = actual.max()
    for month, val in forecast.items():
        if val < 0:
            log.error("SANITY FAIL [%s]: negative forecast %.2f for %s", company_code, val, month)
        elif val > 2 * hist_max:
            log.warning(
                "SANITY WARN [%s]: forecast %.2fM exceeds 2× historical max %.2fM for %s",
                company_code, val / 1e6, hist_max / 1e6, month,
            )
        else:
            log.info("SANITY OK [%s]: forecast %.2fM for %s", company_code, val / 1e6, month)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log.info("Starting monthly sales forecast (Holt-Winters)")

    df = load_monthly_data()

    companies = df["company_code"].unique()
    log.info("Companies found: %s", list(companies))

    summary_rows = []

    for code in sorted(companies):
        name = df[df["company_code"] == code]["company_name"].iloc[0]
        slug = code.lower()  # e.g. "syriatel" or "mtn"

        series = build_series(df, code)
        log.info("Series for %s: %d months (%s to %s)", code, len(series), series.index[0].strftime("%Y-%m"), series.index[-1].strftime("%Y-%m"))

        fit, fitted, forecast = fit_forecast(series, code)
        metrics = compute_metrics(series, fitted)

        log.info(
            "[%s] In-sample RMSE: %.2f SYP | MAPE: %.2f%%",
            code, metrics["rmse"], metrics["mape"],
        )

        sanity_check(series, forecast, code)

        # Save PNG
        png_path = SCREENSHOTS_DIR / f"forecast-{slug}.png"
        plot_forecast(series, fitted, forecast, name, code, png_path, metrics)

        # Save CSV
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        csv_rows = []
        for period, val in series.items():
            csv_rows.append({"period": period.strftime("%Y-%m"), "type": "actual", "sales_syp": float(val)})
        for period, val in fitted.items():
            csv_rows.append({"period": period.strftime("%Y-%m"), "type": "fitted", "sales_syp": float(val)})
        for period, val in forecast.items():
            csv_rows.append({"period": period.strftime("%Y-%m"), "type": "forecast", "sales_syp": float(val)})

        csv_path = OUTPUT_DIR / f"forecast-{slug}.csv"
        pd.DataFrame(csv_rows).to_csv(csv_path, index=False)
        log.info("Saved CSV to %s", csv_path)

        # Accumulate for summary printout
        for period, val in forecast.items():
            summary_rows.append({
                "company": name,
                "period": period.strftime("%Y-%m"),
                "forecast_syp": val,
            })
        summary_rows.append({"company": name, "period": "RMSE", "forecast_syp": metrics["rmse"]})
        summary_rows.append({"company": name, "period": "MAPE%", "forecast_syp": metrics["mape"]})

    # Print summary
    print("\n=== Monthly Sales Forecast Summary ===")
    print(f"Model: Holt-Winters (trend='add', seasonal=None)")
    print(f"Reason for no seasonality: only ~12 months of data; seasonal fit requires ≥24 months.")
    print()
    for code in sorted(companies):
        name = df[df["company_code"] == code]["company_name"].iloc[0]
        rows = [r for r in summary_rows if r["company"] == name]
        print(f"--- {name} ---")
        for r in rows:
            if r["period"] in ("RMSE", "MAPE%"):
                if r["period"] == "RMSE":
                    print(f"  In-sample RMSE: {r['forecast_syp']/1e6:.3f}M SYP")
                else:
                    print(f"  In-sample MAPE: {r['forecast_syp']:.2f}%")
            else:
                print(f"  Forecast {r['period']}: {r['forecast_syp']/1e6:.3f}M SYP")
        print()

    print(
        "NOTE: These forecasts are illustrative of the technique, not planning inputs.\n"
        "      12 months of data is too short for confident forecasting; confidence intervals\n"
        "      would be wide, and no seasonal pattern can be identified at this data volume."
    )


if __name__ == "__main__":
    main()
