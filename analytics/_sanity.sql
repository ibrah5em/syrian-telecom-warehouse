-- ============================================================
-- Analytics Sanity Checks
-- All rows must return 't'. If any return 'f', fix the query.
-- ============================================================

-- 1. Q1 totals sum to the raw fact total
SELECT
    (SELECT SUM(total_amount_syp) FROM dw.fact_sales)::numeric
    =
    (SELECT SUM(total_sales_syp) FROM (
        SELECT SUM(f.total_amount_syp) AS total_sales_syp
        FROM dw.fact_sales f
        JOIN dw.dim_company co ON co.company_sk = f.company_sk
        GROUP BY co.company_code
    ) q1)::numeric
    AS q1_matches_raw;

-- 2. Q4 monthly totals sum to the raw fact total
SELECT
    (SELECT SUM(total_amount_syp) FROM dw.fact_sales)::numeric
    =
    (SELECT SUM(sales_syp) FROM (
        SELECT SUM(f.total_amount_syp) AS sales_syp
        FROM dw.fact_sales f
        JOIN dw.dim_date d  ON d.date_sk = f.date_sk
        JOIN dw.dim_company co ON co.company_sk = f.company_sk
        GROUP BY d.year, d.month, co.company_code
    ) q4)::numeric
    AS q4_matches_raw;

-- 3. Every fact row has a valid date_sk in dim_date
SELECT
    NOT EXISTS (
        SELECT 1 FROM dw.fact_sales f
        LEFT JOIN dw.dim_date d ON d.date_sk = f.date_sk
        WHERE d.date_sk IS NULL
    ) AS all_facts_have_valid_date;

-- 4. Every fact row's company_sk resolves
SELECT
    NOT EXISTS (
        SELECT 1 FROM dw.fact_sales f
        LEFT JOIN dw.dim_company c ON c.company_sk = f.company_sk
        WHERE c.company_sk IS NULL
    ) AS all_facts_have_valid_company;

-- 5. fact_sales total_amount equals quantity * unit_price (within 0.01 SYP for rounding)
SELECT
    NOT EXISTS (
        SELECT 1 FROM dw.fact_sales
        WHERE ABS(total_amount_syp - (quantity * unit_price_syp)) > 0.01
    ) AS total_matches_qty_times_price;

-- 6. dim_company has exactly 2 rows
SELECT (SELECT COUNT(*) FROM dw.dim_company) = 2 AS dim_company_has_two_rows;

-- 7. dim_date covers at least 5 years
SELECT (SELECT COUNT(*) FROM dw.dim_date) >= 1825 AS dim_date_has_five_years;
