-- ============================================================
-- Query: Sales by City (with company breakdown)
-- Question: Which cities generate the most revenue, and how does it split between operators?
-- Inputs:   dw.fact_sales, dw.dim_customer, dw.dim_company
-- Output:   ~14 rows × 5 cols (city, syriatel_syp, mtn_syp, total_syp, unique_customers)
-- Notes:    Customer city is used (not OLTP-time city, since we have only the
--           DW snapshot). Cross-tab via CASE WHEN.
-- ============================================================

SELECT
    c.city,
    SUM(CASE WHEN co.company_code = 'SYRIATEL' THEN f.total_amount_syp ELSE 0 END) AS syriatel_syp,
    SUM(CASE WHEN co.company_code = 'MTN'      THEN f.total_amount_syp ELSE 0 END) AS mtn_syp,
    SUM(f.total_amount_syp)               AS total_syp,
    COUNT(DISTINCT c.customer_sk)         AS unique_customers
FROM dw.fact_sales   AS f
JOIN dw.dim_customer AS c  ON c.customer_sk = f.customer_sk
JOIN dw.dim_company  AS co ON co.company_sk = f.company_sk
GROUP BY c.city
ORDER BY total_syp DESC;
