-- ============================================================
-- Query: Company Comparison
-- Question: Side-by-side performance comparison across operators.
-- Inputs:   dw.fact_sales, dw.dim_company, dw.dim_customer, dw.dim_product
-- Output:   2 rows × ~7 cols (revenue, orders, customers, AOV, cities, categories)
-- Notes:    Pure aggregations grouped by company.
-- ============================================================

SELECT
    co.company_code,
    co.company_name_en,
    SUM(f.total_amount_syp)                AS total_revenue_syp,
    COUNT(*)                                AS order_count,
    COUNT(DISTINCT f.customer_sk)           AS customer_count,
    ROUND(AVG(f.total_amount_syp), 2)       AS avg_order_value_syp,
    COUNT(DISTINCT c.city)                  AS cities_served,
    COUNT(DISTINCT p.category)              AS categories_sold,
    ROUND(SUM(f.total_amount_syp)::numeric
          / NULLIF(COUNT(DISTINCT f.customer_sk), 0), 2)  AS revenue_per_customer_syp
FROM dw.fact_sales   AS f
JOIN dw.dim_company  AS co ON co.company_sk  = f.company_sk
JOIN dw.dim_customer AS c  ON c.customer_sk  = f.customer_sk
JOIN dw.dim_product  AS p  ON p.product_sk   = f.product_sk
GROUP BY co.company_code, co.company_name_en
ORDER BY total_revenue_syp DESC;
