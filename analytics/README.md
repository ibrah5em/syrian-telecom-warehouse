# Analytics — the six required queries

Each query answers one of the business questions called out in the brief. Each file begins with a standardized header (Question / Inputs / Output / Notes) — read those before running.

| # | File | Used by report section | Used by dashboard |
|---|---|---|---|
| 1 | `01_total_sales_per_company.sql`  | §4 النتائج — Revenue summary | Pie chart |
| 2 | `02_top_customers.sql`            | §4 النتائج — Customer concentration | Table |
| 3 | `03_sales_by_city.sql`            | §4 النتائج — Geographic spread | Stacked bar |
| 4 | `04_monthly_sales.sql`            | §4 النتائج — Trend analysis | Line chart |
| 5 | `05_company_comparison.sql`       | §4 النتائج — Operator side-by-side | KPI grid |
| 6 | `06_decision_indicators.sql`      | §4 النتائج — Recommendations | Number cards |

## Running

```bash
make analytics
```

Or one at a time:
```bash
docker exec -i telecom_dw psql -U dw -d telecom_dw < analytics/01_total_sales_per_company.sql
```

## Sanity

`_sanity.sql` cross-checks Q1 and Q4 totals against the raw fact table, and validates fact integrity. All rows must return `t`. Run after any ETL change.

## Performance

Every query should complete in under 2 seconds on the seeded dataset. If one doesn't:
1. Check `EXPLAIN ANALYZE` output
2. Coordinate with the `dw-architect` agent to add an index
3. Re-run after the index is in place
