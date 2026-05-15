-- ============================================================
-- MTN Syria OLTP — Sales System
-- ============================================================
-- Design intent (DIVERGENCE):
--   - Table naming:   clients / items / transactions
--   - Primary keys:   UUID
--   - City storage:   English VARCHAR (inline, no lookup table)
--   - Phone format:   National (0XX...)
--   - Price type:     NUMERIC(12,2)
--   - Order total:    NOT STORED — ETL must compute
--   - Date storage:   separate DATE + TIME columns
--   - Category case:  UPPER (INTERNET / VOICE / BUNDLE)
--   - Product names:  English
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS clients (
    client_id      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    client_name    VARCHAR(200) NOT NULL,
    msisdn         VARCHAR(15)  NOT NULL UNIQUE,
    city_en        VARCHAR(50)  NOT NULL,
    registered_at  DATE         NOT NULL DEFAULT CURRENT_DATE,
    inserted_ts    TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_msisdn_national CHECK (msisdn ~ '^09[0-9]{8}$')
);

CREATE INDEX idx_clients_msisdn ON clients(msisdn);
CREATE INDEX idx_clients_city   ON clients(city_en);

CREATE TABLE IF NOT EXISTS items (
    item_id     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    item_name   VARCHAR(200) NOT NULL,
    item_type   VARCHAR(50)  NOT NULL,
    price_syp   NUMERIC(12,2) NOT NULL CHECK (price_syp > 0),
    CONSTRAINT chk_item_type CHECK (item_type IN ('INTERNET', 'VOICE', 'BUNDLE'))
);

CREATE TABLE IF NOT EXISTS transactions (
    tx_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id    UUID          NOT NULL REFERENCES clients(client_id),
    item_id      UUID          NOT NULL REFERENCES items(item_id),
    qty          INTEGER       NOT NULL CHECK (qty > 0),
    price_at_tx  NUMERIC(12,2) NOT NULL CHECK (price_at_tx > 0),
    tx_date      DATE          NOT NULL,
    tx_time      TIME          NOT NULL,
    inserted_ts  TIMESTAMP     NOT NULL DEFAULT NOW()
    -- NOTE: No total column. ETL must compute qty * price_at_tx.
);

CREATE INDEX idx_transactions_client ON transactions(client_id);
CREATE INDEX idx_transactions_item   ON transactions(item_id);
CREATE INDEX idx_transactions_date   ON transactions(tx_date);

COMMENT ON TABLE  clients      IS 'MTN Syria subscriber base';
COMMENT ON TABLE  items        IS 'Catalog of telecom offerings';
COMMENT ON TABLE  transactions IS 'Sales records — total derived in ETL as qty * price_at_tx';
