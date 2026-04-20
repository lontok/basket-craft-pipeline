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

# Load all MySQL tables as-is into AWS RDS Postgres (raw layer only, no transforms)
python load_raw_to_rds.py

# Copy the RDS raw schema into Snowflake's raw schema (no transforms)
python load_rds_to_snowflake.py

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_transform.py -v

# Run a single test
pytest tests/test_transform.py::test_monthly_summary_aggregates_correctly -v

# Connect to local Postgres
PGPASSWORD=pipeline_pass psql -h localhost -U pipeline -d basket_craft_dw

# Connect to AWS RDS (credentials are in .env)
PGPASSWORD="$RDS_PASSWORD" psql -h "$RDS_HOST" -U "$RDS_USER" -d "$RDS_DATABASE"
```

## Architecture

The pipeline follows an ELT pattern with two Postgres schemas:

1. **Extract**: `pipeline/extract.py` reads 3 tables from MySQL (`orders`, `order_items`, `products`) using pandas `read_sql_table`, validates source schema for drift, then truncates and loads into the Postgres `raw` schema.
2. **Transform**: `pipeline/transform.py` executes `sql/monthly_summary.sql`, which aggregates `raw.order_items` joined to `raw.products` into `analytics.monthly_sales_summary` (grouped by month and product).

Each run is idempotent — tables are truncated before loading, so re-runs produce identical results.

**Data flow**: MySQL → Python (SQLAlchemy/pandas) → Postgres `raw.*` → SQL transform → Postgres `analytics.monthly_sales_summary`

### AWS RDS Raw Load

Alongside the local Docker Postgres target, the repository also loads the full raw layer into an AWS RDS PostgreSQL instance. This path applies no transformations.

The script `load_raw_to_rds.py` runs separately from `run_pipeline.py`. It uses SQLAlchemy's `inspect()` to list every table in MySQL at runtime, so new source tables get picked up automatically without code changes. Each destination table is written with `pandas.to_sql(if_exists="replace")`, which drops and recreates the table from pandas-inferred types — no pre-existing DDL is required on RDS. All tables land in `raw.<table_name>`.

Only the extract-load half runs against RDS; the `analytics.monthly_sales_summary` transform still targets the local Dockerized Postgres.

**Data flow (RDS variant)**: MySQL → Python (SQLAlchemy/pandas) → RDS `raw.*`

### Snowflake Raw Load

A third destination copies the RDS raw layer into Snowflake with no transformations. The script `load_rds_to_snowflake.py` runs separately from `run_pipeline.py` and `load_raw_to_rds.py`.

The target is the `BASKET_CRAFT` database and the `RAW` schema (accessible as `basket_craft.raw` in unquoted SQL since Snowflake folds unquoted identifiers to uppercase). The `RAW` schema must already exist before the loader runs. The loader's role (`basket_craft_loader`) has `CREATE TABLE` on the schema but not `CREATE SCHEMA` on the database, so an admin provisions the schema and grants once per environment; the script only fills it in. The loader does not attempt `CREATE SCHEMA IF NOT EXISTS`, since that call would fail under least-privilege.

For each table in RDS's `raw` schema (discovered via `inspect(engine).get_table_names(schema="raw")`), the script reads all rows into a pandas DataFrame with `read_sql_table`, then calls `snowflake.connector.pandas_tools.write_pandas` with `overwrite=True`, `auto_create_table=True`, and `quote_identifiers=False`. `write_pandas` stages a Parquet file to Snowflake's internal stage and issues `COPY INTO`, which is much faster than row-by-row inserts. Table and column names are uppercased so queries like `SELECT * FROM raw.orders` resolve without quoted identifiers.

To run the loader, activate the virtual environment (`source venv/bin/activate`), install requirements once (`pip install -r requirements.txt`), then run `python load_rds_to_snowflake.py`. The script reads connection details from `.env`: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_ROLE`. `SNOWFLAKE_SCHEMA` is optional and defaults to `RAW`. `.env` is gitignored, so no secrets are committed.

**Data flow (Snowflake variant)**: MySQL → RDS `raw.*` (via `load_raw_to_rds.py`) → Snowflake `BASKET_CRAFT.RAW.*` (via `load_rds_to_snowflake.py`)

## Key Design Decisions

- Products serve as categories (4 gift baskets, no separate category table).
- Revenue is gross only (`order_items.price_usd`); refunds are not subtracted.
- `config.py` uses `load_dotenv(override=True)` so `.env` always takes precedence over shell environment variables.
- Transform SQL lives in `sql/` files, not embedded in Python — edit the SQL directly to change business logic.
- `pipeline/config.py` exposes four connection factories: `get_mysql_engine()`, `get_postgres_engine()` (local Docker), `get_rds_engine()` (AWS RDS), and `get_snowflake_connection()` (Snowflake). The RDS helper reads `RDS_HOST`, `RDS_PORT`, `RDS_USER`, `RDS_PASSWORD`, and `RDS_DATABASE` from `.env`. The Snowflake helper reads `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, optional `SNOWFLAKE_SCHEMA` (default `RAW`), and optional `SNOWFLAKE_ROLE`.
- `get_snowflake_connection()` imports `snowflake.connector` lazily inside the function so `pipeline/config.py` stays importable when the Snowflake connector isn't installed — only the Snowflake loader path pays the dependency cost.
- The RDS raw-load uses `if_exists="replace"` rather than the local pipeline's `TRUNCATE + append` because destination DDL is not pre-created on RDS. Types are inferred by pandas, so some columns may differ slightly from MySQL (e.g., `DATETIME` lands as `TIMESTAMP WITHOUT TIME ZONE`).
- The Snowflake raw-load uses `write_pandas(overwrite=True, auto_create_table=True)`, which issues a `CREATE OR REPLACE TABLE` and a `COPY INTO` per table. Destination DDL is not pre-created on Snowflake; types are inferred from pandas dtypes. This matches the RDS loader's idempotent drop-and-reload semantics.

## Testing

Tests require the Docker Postgres container to be running. The `pg_engine` fixture (session-scoped in `tests/conftest.py`) creates schemas and tables automatically. The `seed_raw_data` fixture inserts small fixture data and cleans up after each test. Extract tests use pytest-mock to avoid hitting MySQL.
