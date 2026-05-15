-- ============================================================
-- Unified Data Warehouse — Telecom DW
-- ============================================================
-- Star schema: 4 dimensions + 1 fact + ETL operational tables.
-- SCD policy: Type 1 (overwrite). See CLAUDE.md §3.
-- All money in SYP, all timestamps UTC.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS dw;

SET search_path TO dw, public;

-- ----------------------------------------------------------
-- dim_company
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_company (
    company_sk      SERIAL      PRIMARY KEY,
    company_code    TEXT        NOT NULL UNIQUE,
    company_name_ar TEXT        NOT NULL,
    company_name_en TEXT        NOT NULL,
    etl_loaded_at   TIMESTAMP   NOT NULL DEFAULT NOW(),
    etl_batch_id    UUID        NOT NULL DEFAULT gen_random_uuid()
);

INSERT INTO dim_company (company_code, company_name_ar, company_name_en) VALUES
    ('SYRIATEL', 'سيرياتل',  'Syriatel'),
    ('MTN',      'إم تي إن', 'MTN Syria')
ON CONFLICT (company_code) DO NOTHING;

-- ----------------------------------------------------------
-- dim_date
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_date (
    date_sk      INTEGER  PRIMARY KEY,   -- YYYYMMDD
    full_date    DATE     NOT NULL UNIQUE,
    year         INTEGER  NOT NULL,
    quarter      INTEGER  NOT NULL,
    month        INTEGER  NOT NULL,
    month_name   TEXT     NOT NULL,
    day          INTEGER  NOT NULL,
    day_of_week  INTEGER  NOT NULL,
    is_weekend   BOOLEAN  NOT NULL       -- Fri/Sat in Syria
);

-- Populate 2022-01-01 to 2026-12-31
INSERT INTO dim_date (date_sk, full_date, year, quarter, month, month_name, day, day_of_week, is_weekend)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT,
    d::DATE,
    EXTRACT(YEAR FROM d)::INT,
    EXTRACT(QUARTER FROM d)::INT,
    EXTRACT(MONTH FROM d)::INT,
    TRIM(TO_CHAR(d, 'Month')),
    EXTRACT(DAY FROM d)::INT,
    EXTRACT(DOW FROM d)::INT,
    (EXTRACT(DOW FROM d)::INT IN (5, 6))
FROM generate_series('2022-01-01'::date, '2026-12-31'::date, '1 day'::interval) d
ON CONFLICT (date_sk) DO NOTHING;

-- ----------------------------------------------------------
-- dim_customer
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_sk          SERIAL      PRIMARY KEY,
    source_system        TEXT        NOT NULL,
    source_customer_id   TEXT        NOT NULL,
    full_name            TEXT        NOT NULL,
    phone_e164           TEXT        NOT NULL,
    city                 TEXT        NOT NULL,
    signup_date          DATE        NOT NULL,
    etl_loaded_at        TIMESTAMP   NOT NULL DEFAULT NOW(),
    etl_batch_id         UUID        NOT NULL,
    UNIQUE (source_system, source_customer_id)
);

CREATE INDEX idx_dim_customer_phone ON dim_customer(phone_e164);
CREATE INDEX idx_dim_customer_city  ON dim_customer(city);

-- ----------------------------------------------------------
-- dim_product
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_product (
    product_sk          SERIAL        PRIMARY KEY,
    source_system       TEXT          NOT NULL,
    source_product_id   TEXT          NOT NULL,
    product_name_en     TEXT          NOT NULL,
    category            TEXT          NOT NULL CHECK (category IN ('INTERNET', 'VOICE', 'BUNDLE')),
    unit_price_syp      NUMERIC(14,2) NOT NULL,
    etl_loaded_at       TIMESTAMP     NOT NULL DEFAULT NOW(),
    etl_batch_id        UUID          NOT NULL,
    UNIQUE (source_system, source_product_id)
);

-- ----------------------------------------------------------
-- fact_sales
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_sales (
    sale_sk           BIGSERIAL     PRIMARY KEY,
    date_sk           INTEGER       NOT NULL REFERENCES dim_date(date_sk),
    customer_sk       INTEGER       NOT NULL REFERENCES dim_customer(customer_sk),
    product_sk        INTEGER       NOT NULL REFERENCES dim_product(product_sk),
    company_sk        INTEGER       NOT NULL REFERENCES dim_company(company_sk),
    quantity          INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price_syp    NUMERIC(14,2) NOT NULL,
    total_amount_syp  NUMERIC(14,2) NOT NULL,
    source_order_id   TEXT          NOT NULL,
    etl_loaded_at     TIMESTAMP     NOT NULL DEFAULT NOW(),
    etl_batch_id      UUID          NOT NULL,
    UNIQUE (company_sk, source_order_id)
);

CREATE INDEX idx_fact_sales_date         ON fact_sales(date_sk);
CREATE INDEX idx_fact_sales_customer     ON fact_sales(customer_sk);
CREATE INDEX idx_fact_sales_product      ON fact_sales(product_sk);
CREATE INDEX idx_fact_sales_company      ON fact_sales(company_sk);
CREATE INDEX idx_fact_sales_company_date ON fact_sales(company_sk, date_sk);

COMMENT ON TABLE fact_sales IS
'Grain: one row per order line per operator. Each row is a single product purchase by a single customer through a single operator on a single date.';

-- ----------------------------------------------------------
-- Operational: ETL run audit + error quarantine
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_runs (
    batch_id          UUID        PRIMARY KEY,
    started_at        TIMESTAMP   NOT NULL,
    finished_at       TIMESTAMP,
    rows_extracted    INTEGER     NOT NULL DEFAULT 0,
    rows_loaded       INTEGER     NOT NULL DEFAULT 0,
    rows_quarantined  INTEGER     NOT NULL DEFAULT 0,
    status            TEXT        NOT NULL CHECK (status IN ('running','succeeded','failed')),
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS etl_errors (
    error_id      BIGSERIAL   PRIMARY KEY,
    batch_id      UUID        NOT NULL REFERENCES etl_runs(batch_id),
    source_system TEXT        NOT NULL,
    source_table  TEXT        NOT NULL,
    source_row    JSONB       NOT NULL,
    reason        TEXT        NOT NULL,
    occurred_at   TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_etl_errors_batch  ON etl_errors(batch_id);
CREATE INDEX idx_etl_errors_reason ON etl_errors(reason);
