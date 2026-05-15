-- RFM (Recency, Frequency, Monetary) raw values per customer
-- Recency: days from customer's last purchase to the dataset's MAX(full_date).
--   Using dataset max (not NOW()) ensures reproducibility.
-- Frequency: total order count over the full period.
-- Monetary: total spend in SYP.
-- Scores 1–5 are derived via NTILE(5) in the calling script (pandas qcut with rank).
-- This SQL returns the raw RFM values; scoring and labeling happen in rfm_segment.py.

WITH ref AS (
    SELECT MAX(d.full_date) AS as_of_date
    FROM fact_sales f
    JOIN dim_date d ON d.date_sk = f.date_sk
),
rfm_raw AS (
    SELECT
        f.customer_sk,
        dc.full_name,
        dc.city,
        dc.source_system,
        co.company_name_en                                   AS company,
        co.company_code,
        (ref.as_of_date - MAX(d.full_date))::integer         AS recency_days,
        COUNT(f.sale_sk)                                     AS frequency,
        SUM(f.total_amount_syp)                              AS monetary_syp
    FROM fact_sales f
    JOIN dim_date     d  ON d.date_sk     = f.date_sk
    JOIN dim_customer dc ON dc.customer_sk = f.customer_sk
    JOIN dim_company  co ON co.company_sk  = f.company_sk
    CROSS JOIN ref
    GROUP BY
        f.customer_sk,
        dc.full_name,
        dc.city,
        dc.source_system,
        co.company_name_en,
        co.company_code,
        ref.as_of_date
),
rfm_scored AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY recency_days DESC)  AS r_score,  -- lower days = more recent = higher score
        NTILE(5) OVER (ORDER BY frequency ASC)       AS f_score,
        NTILE(5) OVER (ORDER BY monetary_syp ASC)    AS m_score
    FROM rfm_raw
)
SELECT
    customer_sk,
    full_name,
    city,
    source_system,
    company,
    company_code,
    recency_days,
    frequency,
    monetary_syp,
    r_score,
    f_score,
    m_score,
    (r_score::text || f_score::text || m_score::text) AS rfm_code
FROM rfm_scored
ORDER BY customer_sk;
