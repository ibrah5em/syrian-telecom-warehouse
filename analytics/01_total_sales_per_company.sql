-- ============================================================
-- Query: Total Sales per Company
-- Question: How much total revenue does each operator generate, and what share?
-- Inputs:   dw.fact_sales, dw.dim_company
-- Output:   2 rows, columns (company_code, company_name_en, total_sales_syp, order_count, share_pct)
-- Notes:    Headline revenue indicator for the Ministry.
-- ============================================================

WITH company_totals AS (
    SELECT
        co.company_code,
        co.company_name_en,
        SUM(f.total_amount_syp) AS total_sales_syp,
        COUNT(*)                AS order_count
    FROM dw.fact_sales AS f
    JOIN dw.dim_company AS co ON co.company_sk = f.company_sk
    GROUP BY co.company_code, co.company_name_en
)
SELECT
    company_code,
    company_name_en,
    total_sales_syp,
    order_count,
    ROUND(100.0 * total_sales_syp / SUM(total_sales_syp) OVER (), 2) AS share_pct
FROM company_totals
ORDER BY total_sales_syp DESC;
