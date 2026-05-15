-- ============================================================
-- Query: Decision Indicators (composite KPIs for the Ministry)
-- Question: What are the headline numbers that should drive ministerial decisions?
-- Inputs:   dw.fact_sales, dw.dim_customer, dw.dim_date
-- Output:   single row with composite indicators
-- Notes:    - Revenue concentration: top 10% of customers' share of total
--           - Cities served (geographic breadth)
--           - QoQ growth: last 3 months vs prior 3 months
--           - Grand total
-- ============================================================

WITH per_customer AS (
    SELECT
        f.customer_sk,
        SUM(f.total_amount_syp) AS customer_total
    FROM dw.fact_sales AS f
    GROUP BY f.customer_sk
),
ranked AS (
    SELECT
        customer_total,
        NTILE(10) OVER (ORDER BY customer_total DESC) AS decile
    FROM per_customer
),
top_decile AS (
    SELECT SUM(customer_total) AS top_decile_revenue
    FROM ranked
    WHERE decile = 1
),
totals AS (
    SELECT SUM(customer_total) AS grand_total FROM per_customer
),
ref_date AS (
    SELECT MAX(d.full_date) AS as_of
    FROM dw.dim_date d
    JOIN dw.fact_sales f ON f.date_sk = d.date_sk
),
trend AS (
    SELECT
        SUM(CASE
            WHEN d.full_date >  (SELECT as_of FROM ref_date) - INTERVAL '3 months'
            THEN f.total_amount_syp ELSE 0
        END) AS last_3m,
        SUM(CASE
            WHEN d.full_date <= (SELECT as_of FROM ref_date) - INTERVAL '3 months'
             AND d.full_date >  (SELECT as_of FROM ref_date) - INTERVAL '6 months'
            THEN f.total_amount_syp ELSE 0
        END) AS prior_3m
    FROM dw.fact_sales f
    JOIN dw.dim_date d ON d.date_sk = f.date_sk
)
SELECT
    ROUND(100.0 * td.top_decile_revenue / NULLIF(t.grand_total, 0), 2)
                                                          AS top_10pct_customer_revenue_share_pct,
    (SELECT COUNT(DISTINCT city) FROM dw.dim_customer)    AS cities_served,
    (SELECT COUNT(*) FROM dw.dim_customer)                AS total_customers,
    ROUND(100.0 * (tr.last_3m - tr.prior_3m) / NULLIF(tr.prior_3m, 0), 2)
                                                          AS qoq_growth_pct,
    tr.last_3m                                            AS last_3m_revenue_syp,
    tr.prior_3m                                           AS prior_3m_revenue_syp,
    t.grand_total                                         AS total_revenue_syp
FROM top_decile td, totals t, trend tr;
