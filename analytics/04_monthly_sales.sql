-- ============================================================
-- Query: Monthly Sales (with Month-over-Month change)
-- Question: How do monthly revenue trends look for each operator?
-- Inputs:   dw.fact_sales, dw.dim_date, dw.dim_company
-- Output:   one row per (year, month, company); columns include MoM % change
-- Notes:    LAG() window over (company) ordered by (year, month).
--           NULLIF() guards division when previous month is zero.
-- ============================================================

WITH monthly AS (
    SELECT
        d.year,
        d.month,
        co.company_code,
        SUM(f.total_amount_syp) AS sales_syp,
        COUNT(*)                 AS order_count
    FROM dw.fact_sales AS f
    JOIN dw.dim_date    AS d  ON d.date_sk    = f.date_sk
    JOIN dw.dim_company AS co ON co.company_sk = f.company_sk
    GROUP BY d.year, d.month, co.company_code
)
SELECT
    year,
    month,
    company_code,
    sales_syp,
    order_count,
    LAG(sales_syp) OVER (PARTITION BY company_code ORDER BY year, month) AS prev_month_syp,
    ROUND(
        100.0 * (sales_syp - LAG(sales_syp) OVER (PARTITION BY company_code ORDER BY year, month))
        / NULLIF(LAG(sales_syp) OVER (PARTITION BY company_code ORDER BY year, month), 0),
        2
    ) AS mom_change_pct
FROM monthly
ORDER BY company_code, year, month;
