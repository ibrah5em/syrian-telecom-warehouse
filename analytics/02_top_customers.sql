-- ============================================================
-- Query: Top 20 Customers
-- Question: Who are the highest-spending customers across both operators?
-- Inputs:   dw.fact_sales, dw.dim_customer, dw.dim_date
-- Output:   20 rows, columns (customer_sk, full_name, source_system, city,
--           total_spent_syp, order_count, avg_order_syp, first_order, last_order)
-- Notes:    Cross-operator aggregation. Customers are NOT deduplicated across
--           Syriatel/MTN — they're treated as separate identities since we have
--           no reliable cross-operator identity (would require phone matching).
-- ============================================================

SELECT
    c.customer_sk,
    c.full_name,
    c.source_system,
    c.city,
    SUM(f.total_amount_syp)            AS total_spent_syp,
    COUNT(*)                            AS order_count,
    ROUND(AVG(f.total_amount_syp), 2)  AS avg_order_syp,
    MIN(d.full_date)                    AS first_order_date,
    MAX(d.full_date)                    AS last_order_date
FROM dw.fact_sales AS f
JOIN dw.dim_customer AS c ON c.customer_sk = f.customer_sk
JOIN dw.dim_date     AS d ON d.date_sk    = f.date_sk
GROUP BY c.customer_sk, c.full_name, c.source_system, c.city
ORDER BY total_spent_syp DESC
LIMIT 20;
