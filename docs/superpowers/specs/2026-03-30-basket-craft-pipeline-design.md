# Basket Craft Sales Pipeline — Design Spec

## Overview

A monthly sales data pipeline that extracts order data from the Basket Craft MySQL database and loads it into a local PostgreSQL instance running in Docker. The pipeline produces a summary table with revenue, order counts, and average order value broken down by product and month.

## Source

- **Database:** MySQL (`basket_craft`) hosted at `db.isba.co:3306`
- **Tables extracted:**
  - `orders` — order-level records with `order_id`, `created_at`, `user_id`, `price_usd`, `cogs_usd`, `items_purchased`
  - `order_items` — line-item records with `order_item_id`, `order_id`, `product_id`, `is_primary_item`, `price_usd`, `cogs_usd`
  - `products` — product catalog with `product_id`, `product_name`, `description`
- **Volume:** ~32K orders across 4 products, spanning Mar 2023 – Mar 2026
- **Products (used as categories):**
  1. The Original Gift Basket
  2. The Valentine's Gift Basket
  3. The Birthday Gift Basket
  4. The Holiday Gift Basket

## Destination

- **Database:** PostgreSQL running in a Docker container via Docker Compose
- **Schemas:**
  - `raw` — mirror of extracted MySQL tables (staging layer)
  - `analytics` — transformed summary tables

## Architecture

ELT pattern. Python handles extraction and loading into the `raw` schema. SQL handles the transformation from `raw` to `analytics`.

```
MySQL (basket_craft)
  │
  ▼  Python + SQLAlchemy (extract)
  │
Postgres raw schema
  │  orders, order_items, products
  │
  ▼  SQL transform (monthly_summary.sql)
  │
Postgres analytics schema
     monthly_sales_summary
```

### Pipeline Tooling

- Pure Python scripts — no orchestrator (Prefect, Dagster, Airflow, etc.)
- SQLAlchemy for database connections
- pandas for data movement (`read_sql` → `to_sql`)
- psycopg2 as the Postgres driver
- python-dotenv for credential management

### Trigger

Manual only. Run `python run_pipeline.py` when fresh data is needed.

## Output Table

`analytics.monthly_sales_summary`

| Column | Type | Description |
|--------|------|-------------|
| `month` | DATE | First day of the month |
| `product_name` | VARCHAR | Product name (serves as category) |
| `total_revenue` | DECIMAL(12,2) | Gross revenue — sum of `order_items.price_usd` |
| `order_count` | INTEGER | Count of distinct orders containing this product |
| `avg_order_value` | DECIMAL(10,2) | `total_revenue / order_count` |
| `total_items_sold` | INTEGER | Count of order item rows for this product |
| `loaded_at` | TIMESTAMP | Pipeline execution timestamp |

### Revenue Definition

- **Gross revenue only.** Sum of `order_items.price_usd` grouped by product and month.
- Refunds (`order_item_refunds`) are not subtracted — out of scope for this pipeline.
- Aggregation is at the `order_items` level joined to `products`, which correctly attributes revenue per product in multi-item orders.

## Project Structure

```
basket-craft-pipeline/
├── docker-compose.yml          # Postgres container
├── requirements.txt            # Python dependencies
├── .env                        # Connection credentials (not committed)
├── run_pipeline.py             # Entry point
├── pipeline/
│   ├── __init__.py
│   ├── extract.py              # MySQL → raw schema
│   ├── transform.py            # raw → analytics schema
│   └── config.py               # DB connection setup
├── sql/
│   ├── create_schemas.sql      # DDL for raw + analytics schemas
│   └── monthly_summary.sql     # Transform query
└── tests/
    ├── conftest.py             # Postgres fixtures
    └── test_pipeline.py        # Unit + smoke tests
```

## Infrastructure

### Docker Compose

A single `docker-compose.yml` that runs PostgreSQL. Credentials are read from `.env`.

- Postgres image: `postgres:16`
- Exposed port: `5432`
- Persistent volume for data
- Environment variables for `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

### Environment Variables (`.env`)

The `.env` file holds credentials for both databases:

- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` — source connection
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — destination connection

## Error Handling

- **Connection failures:** Log the error and exit with a non-zero code. No automatic retries — re-run manually.
- **Schema drift:** Before loading, verify that expected source columns exist in the MySQL tables. Fail fast with a clear message if the schema has changed.
- **Idempotent loads:** Each run truncates `raw` tables and rebuilds `analytics.monthly_sales_summary` from scratch. Safe to re-run without risk of duplicates or partial state.

## Testing

- **Framework:** pytest
- **Unit tests:** Load a small fixture dataset into the Dockerized Postgres `raw` schema, run the transform SQL, and verify the summary table has correct aggregations.
- **Smoke test:** End-to-end run that extracts a small sample from MySQL, loads into Postgres, and verifies the summary table has expected columns and non-null values.
- **Test infrastructure:** Uses the same Docker Postgres instance as the pipeline.

## Out of Scope

- Dashboard / visualization layer
- Refund-adjusted (net) revenue
- Incremental / CDC extraction
- Scheduling / orchestration
- Alerting / notifications
