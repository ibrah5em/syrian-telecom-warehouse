-- ============================================================
-- Syriatel OLTP — Sales System
-- ============================================================
-- Design intent (DIVERGENCE):
--   - Table naming:   customers / products / orders
--   - Primary keys:   SERIAL integer
--   - City storage:   Arabic VARCHAR
--   - Phone format:   E.164 (+963...)
--   - Price type:     INTEGER (whole SYP)
--   - Order total:    STORED (precomputed in app layer)
--   - Date storage:   single TIMESTAMP
--   - Category case:  Title Case (Internet / Voice / Bundle)
--   - Product names:  Arabic
-- ============================================================

CREATE TABLE IF NOT EXISTS cities (
    city_id    SERIAL PRIMARY KEY,
    city_ar    VARCHAR(50) NOT NULL UNIQUE,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id   SERIAL PRIMARY KEY,
    full_name     VARCHAR(200) NOT NULL,
    phone         VARCHAR(20)  NOT NULL UNIQUE,
    city_id       INTEGER      NOT NULL REFERENCES cities(city_id),
    signup_date   TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_phone_e164 CHECK (phone ~ '^\+9639[0-9]{8}$')
);

CREATE INDEX idx_customers_phone ON customers(phone);
CREATE INDEX idx_customers_city  ON customers(city_id);

CREATE TABLE IF NOT EXISTS products (
    product_id    SERIAL PRIMARY KEY,
    product_name  VARCHAR(200) NOT NULL,
    category      VARCHAR(50)  NOT NULL,
    unit_price    INTEGER      NOT NULL CHECK (unit_price > 0),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_category CHECK (category IN ('Internet', 'Voice', 'Bundle'))
);

CREATE TABLE IF NOT EXISTS orders (
    order_id            SERIAL    PRIMARY KEY,
    customer_id         INTEGER   NOT NULL REFERENCES customers(customer_id),
    product_id          INTEGER   NOT NULL REFERENCES products(product_id),
    quantity            INTEGER   NOT NULL CHECK (quantity > 0),
    unit_price_at_sale  INTEGER   NOT NULL CHECK (unit_price_at_sale > 0),
    total_price         INTEGER   NOT NULL CHECK (total_price > 0),
    order_date          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_product  ON orders(product_id);
CREATE INDEX idx_orders_date     ON orders(order_date);

COMMENT ON TABLE  customers IS 'Syriatel retail customers';
COMMENT ON TABLE  products  IS 'Telecom service packages — internet, voice, bundles';
COMMENT ON TABLE  orders    IS 'Sales transactions — total is precomputed at write time';
COMMENT ON COLUMN orders.total_price IS 'Stored = quantity * unit_price_at_sale. ETL must validate.';
