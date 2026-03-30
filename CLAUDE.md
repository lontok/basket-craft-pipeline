# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ELT pipeline that extracts sales data from a remote MySQL database (Basket Craft e-commerce), loads raw tables into a local Dockerized PostgreSQL, and transforms them into a monthly sales summary for dashboard consumption.

## Commands

```bash
# Start Postgres container
docker compose up -d

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the pipeline (extract + transform)
python run_pipeline.py

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_transform.py -v

# Run a single test
pytest tests/test_transform.py::test_monthly_summary_aggregates_correctly -v

# Connect to Postgres
PGPASSWORD=pipeline_pass psql -h localhost -U pipeline -d basket_craft_dw
```

## Architecture

The pipeline follows an ELT pattern with two Postgres schemas:

1. **Extract**: `pipeline/extract.py` reads 3 tables from MySQL (`orders`, `order_items`, `products`) using pandas `read_sql_table`, validates source schema for drift, then truncates and loads into the Postgres `raw` schema.
2. **Transform**: `pipeline/transform.py` executes `sql/monthly_summary.sql`, which aggregates `raw.order_items` joined to `raw.products` into `analytics.monthly_sales_summary` (grouped by month and product).

Each run is idempotent — tables are truncated before loading, so re-runs produce identical results.

**Data flow**: MySQL → Python (SQLAlchemy/pandas) → Postgres `raw.*` → SQL transform → Postgres `analytics.monthly_sales_summary`

## Key Design Decisions

- Products serve as categories (4 gift baskets, no separate category table).
- Revenue is gross only (`order_items.price_usd`); refunds are not subtracted.
- `config.py` uses `load_dotenv(override=True)` so `.env` always takes precedence over shell environment variables.
- Transform SQL lives in `sql/` files, not embedded in Python — edit the SQL directly to change business logic.

## Testing

Tests require the Docker Postgres container to be running. The `pg_engine` fixture (session-scoped in `tests/conftest.py`) creates schemas and tables automatically. The `seed_raw_data` fixture inserts small fixture data and cleans up after each test. Extract tests use pytest-mock to avoid hitting MySQL.
