-- Create schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Raw tables (mirrors of MySQL source)
CREATE TABLE IF NOT EXISTS raw.orders (
    order_id        INTEGER PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL,
    website_session_id INTEGER,
    user_id         INTEGER,
    primary_product_id INTEGER,
    items_purchased SMALLINT NOT NULL,
    price_usd       DECIMAL(6,2) NOT NULL,
    cogs_usd        DECIMAL(6,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.order_items (
    order_item_id   INTEGER PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL,
    order_id        INTEGER,
    product_id      INTEGER,
    is_primary_item SMALLINT NOT NULL,
    price_usd       DECIMAL(6,2) NOT NULL,
    cogs_usd        DECIMAL(6,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.products (
    product_id      INTEGER PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL,
    product_name    VARCHAR(50) NOT NULL,
    description     TEXT
);

-- Analytics table
CREATE TABLE IF NOT EXISTS analytics.monthly_sales_summary (
    month           DATE NOT NULL,
    product_name    VARCHAR(50) NOT NULL,
    total_revenue   DECIMAL(12,2) NOT NULL,
    order_count     INTEGER NOT NULL,
    avg_order_value DECIMAL(10,2) NOT NULL,
    total_items_sold INTEGER NOT NULL,
    loaded_at       TIMESTAMP NOT NULL,
    PRIMARY KEY (month, product_name)
);
