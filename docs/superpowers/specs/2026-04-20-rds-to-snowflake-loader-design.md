# RDS → Snowflake Raw Loader — Design Spec

## Overview

A standalone Python script that copies every table in the AWS RDS PostgreSQL `raw` schema into Snowflake's `raw` schema, preserving row-for-row fidelity and applying no transformations. Runs independently from `run_pipeline.py` (MySQL → local Postgres) and `load_raw_to_rds.py` (MySQL → RDS). The Snowflake loader sits at the end of the RDS hop — it extends the raw-layer replication chain one step further into a cloud warehouse for downstream analytics.

## Source

- **Database:** AWS RDS PostgreSQL (already populated by `load_raw_to_rds.py`)
- **Schema:** `raw`
- **Tables:** every table present in `raw` at runtime — discovered dynamically via `sqlalchemy.inspect(engine).get_table_names(schema="raw")`
- **Rationale for auto-discovery:** the upstream RDS loader also auto-discovers tables from MySQL. Hard-coding a table list in this script would drift out of sync the moment a new table is added to MySQL.

## Destination

- **Database:** Snowflake (account / warehouse / database configured via env vars)
- **Schema:** `RAW` (uppercase — Snowflake's native identifier convention)
- **Table names:** uppercased copies of the RDS table names (`orders` → `ORDERS`)
- **Column names:** uppercased by passing `quote_identifiers=False` to `write_pandas`
- **DDL:** not pre-created; `write_pandas(auto_create_table=True, overwrite=True)` issues a `CREATE OR REPLACE TABLE` each run and infers column types from pandas dtypes

## Architecture

Simple two-step extract-load per table, looped over all discovered tables:

```
RDS Postgres (raw.*)
  │
  ▼  SQLAlchemy + pandas.read_sql_table
  │
  DataFrame in memory
  │
  ▼  snowflake.connector.pandas_tools.write_pandas
  │    (PUT to internal stage → COPY INTO)
  │
Snowflake (RAW.*)
```

### Connector choice

Uses the official `snowflake-connector-python` package with its `write_pandas` helper, not `snowflake-sqlalchemy`'s `to_sql`. The helper serializes the DataFrame to Parquet, PUTs it to an internal stage, then issues `COPY INTO` — bulk load via the server's native ingest path. This is orders of magnitude faster than SQLAlchemy's row-by-row inserts and is the vendor-recommended path for pandas → Snowflake.

### Connection lifecycle

- `sqlalchemy.Engine` (RDS): pooled; no explicit close needed.
- `snowflake.connector.Connection`: not pooled and holds a session token. The script wraps the load in `try / finally` and calls `sf_conn.close()` in the `finally` block to release warehouse resources promptly.

## Components

### `pipeline/config.py` — `get_snowflake_connection()`

New connection factory added alongside `get_mysql_engine()`, `get_postgres_engine()`, and `get_rds_engine()`. Reads env vars and returns a live `snowflake.connector.connection.SnowflakeConnection`.

- **Required env vars:** `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`
- **Optional env vars:** `SNOWFLAKE_SCHEMA` (defaults to `RAW`), `SNOWFLAKE_ROLE` (omitted if unset — connection uses the user's default role)
- **Import strategy:** `snowflake.connector` is imported lazily inside the function body. `pipeline/config.py` is imported by the MySQL→Postgres pipeline and all tests; the lazy import keeps that import graph cheap and keeps the module importable on machines where the Snowflake connector isn't installed.

### `load_rds_to_snowflake.py`

Top-level script. Structure intentionally mirrors `load_raw_to_rds.py` so the two loaders stay visually and mechanically parallel:

1. `get_rds_engine()` — SQLAlchemy engine to RDS
2. `get_snowflake_connection()` — Snowflake connection
3. `ensure_target_schema(conn, schema)` — `CREATE SCHEMA IF NOT EXISTS RAW`
4. `copy_all_tables(rds_engine, sf_conn)` — loop:
   - `inspect(rds_engine).get_table_names(schema="raw")` to enumerate tables
   - `pandas.read_sql_table(table, rds_engine, schema="raw")` for each
   - `write_pandas(sf_conn, df, table_name=table.upper(), schema=TARGET_SCHEMA, auto_create_table=True, overwrite=True, quote_identifiers=False)`
   - raise `RuntimeError` if `write_pandas` returns `success=False`
5. `try / finally` to close the Snowflake connection
6. `sys.exit(1)` on any uncaught exception, matching the RDS loader's failure contract

## Data Flow

```
MySQL (basket_craft)
  │
  ▼  load_raw_to_rds.py    (MySQL → RDS raw.*)
  │
RDS Postgres (raw.*)
  │
  ▼  load_rds_to_snowflake.py   (RDS → Snowflake RAW.*)
  │
Snowflake (RAW.*)
```

The Snowflake loader depends on `load_raw_to_rds.py` having run successfully first. There is no direct MySQL → Snowflake path.

## Idempotency & Error Handling

- **Idempotent:** `overwrite=True` causes `write_pandas` to issue `CREATE OR REPLACE TABLE` each run. Re-running the script produces the same destination state regardless of prior state.
- **All-or-nothing per table, not all-or-nothing across the run:** tables are loaded sequentially. A failure mid-run leaves earlier tables updated and later tables untouched. This matches the RDS loader's behavior and is acceptable because a subsequent successful run restores consistency.
- **Failure surface:** `write_pandas` returns `(success, nchunks, nrows, output)`. The script explicitly checks `success` and raises `RuntimeError` on failure rather than silently continuing.
- **Logging:** `logging` configured at `INFO` level with the same format string as `load_raw_to_rds.py`. Each table logs extraction start, row count, and load completion.

## Configuration

New env vars (to be added to `.env`):

```
SNOWFLAKE_ACCOUNT=<account-locator>
SNOWFLAKE_USER=<user>
SNOWFLAKE_PASSWORD=<password>
SNOWFLAKE_WAREHOUSE=<warehouse-name>
SNOWFLAKE_DATABASE=<database-name>
SNOWFLAKE_SCHEMA=RAW          # optional, defaults to RAW
SNOWFLAKE_ROLE=<role-name>    # optional, uses default if unset
```

New dependency in `requirements.txt`:

```
snowflake-connector-python[pandas]>=3.0,<4.0
```

The `[pandas]` extra pulls in `pyarrow`, which `write_pandas` needs to serialize DataFrames to Parquet for the PUT step.

## Identifier Casing

Postgres folds unquoted identifiers to lowercase; Snowflake folds them to uppercase. The script resolves the mismatch in one direction:

- RDS table names come back lowercase from `get_table_names()`.
- The script uppercases the table name before passing to `write_pandas` and sets `quote_identifiers=False` so column names are also uppercased server-side.
- Net effect: downstream queries against Snowflake can use natural unquoted SQL (`SELECT * FROM raw.orders`) without ever needing double quotes.

## Type Inference

`write_pandas` infers Snowflake column types from pandas dtypes. Consequences worth noting:

- Postgres `TIMESTAMP WITHOUT TIME ZONE` → pandas `datetime64[ns]` → Snowflake `TIMESTAMP_NTZ`
- Postgres `NUMERIC` → pandas `object` (Decimal) → Snowflake `NUMBER(38, 0)` unless precision survives the round-trip
- Postgres `TEXT` / `VARCHAR` → pandas `object` (str) → Snowflake `VARCHAR(16777216)`

Exact target types are not pre-specified; type fidelity is "good enough for raw staging" rather than "exactly preserved." Downstream Snowflake models can cast as needed.

## Out of Scope

- **Transforms in Snowflake:** this spec covers raw load only. `analytics.monthly_sales_summary` remains on local Docker Postgres.
- **Incremental loads / CDC:** full reload only. No watermarking, no merge, no change-data-capture.
- **Key-pair or SSO auth:** password auth only for now. Key-pair can be added later by extending `get_snowflake_connection()`.
- **Parallel table loads:** tables copy sequentially. A ThreadPoolExecutor could be layered in later if table count grows.
- **Schema drift validation:** `load_raw_to_rds.py` has no drift check either; the Snowflake loader does not add one.

## Testing

No new automated tests in this iteration. The existing test suite covers MySQL → local Postgres extraction and transforms; Snowflake is verified by running the script against a real Snowflake account and inspecting the destination tables. If the loader later grows logic worth testing in isolation, the pattern would be:

- Mock `snowflake.connector` / `write_pandas` with `pytest-mock` (same pattern the extract tests use for MySQL).
- Use a small in-memory DataFrame fixture as input.
- Assert `write_pandas` is called with the expected `table_name`, `schema`, `overwrite`, and `quote_identifiers` arguments.

## Commands

```bash
# After adding SNOWFLAKE_* vars to .env and reinstalling deps
pip install -r requirements.txt
python load_rds_to_snowflake.py
```
