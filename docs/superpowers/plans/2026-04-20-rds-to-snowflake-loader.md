# RDS → Snowflake Raw Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone Python script that copies every table from the AWS RDS PostgreSQL `raw` schema into Snowflake's `RAW` schema using the official Snowflake Python connector, with no transformations.

**Architecture:** Auto-discovery loop using `sqlalchemy.inspect` over the RDS `raw` schema, `pandas.read_sql_table` for extraction, and `snowflake.connector.pandas_tools.write_pandas` with `overwrite=True, auto_create_table=True, quote_identifiers=False` for bulk load into uppercase Snowflake identifiers. Connection factory added to `pipeline/config.py` alongside the existing MySQL/Postgres/RDS helpers. Lazy import of `snowflake.connector` inside the factory so other pipeline paths don't pay the import cost. No new automated tests — verification is via a real run against RDS + Snowflake. Idempotency is delegated to `write_pandas`'s `CREATE OR REPLACE TABLE` semantics.

**Tech Stack:** Python 3, SQLAlchemy 2.x, pandas 2.x, psycopg2-binary, `snowflake-connector-python[pandas]` 3.x (new), python-dotenv.

**Testing note:** The approved spec (`docs/superpowers/specs/2026-04-20-rds-to-snowflake-loader-design.md`) explicitly defers automated tests. Each task therefore verifies via syntax compilation, import checks, and a final end-to-end manual smoke test against the real RDS + Snowflake environment rather than TDD red/green steps.

---

## File Structure

- **Create:** `load_rds_to_snowflake.py` — top-level runnable script (mirrors `load_raw_to_rds.py`)
- **Create:** `docs/superpowers/specs/2026-04-20-rds-to-snowflake-loader-design.md` — already written in brainstorming; not re-created here
- **Modify:** `pipeline/config.py` — append `get_snowflake_connection()` after the existing `get_rds_engine()`
- **Modify:** `requirements.txt` — append one line
- **Modify:** `CLAUDE.md` — add command, architecture subsection, and key design decision bullets

Each file has one clear responsibility: `config.py` owns connection factories, the top-level script owns orchestration, `requirements.txt` owns the dependency manifest, `CLAUDE.md` owns project guidance.

---

## Task 1: Add the Snowflake dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append the new line**

Edit `requirements.txt` to add `snowflake-connector-python[pandas]>=3.0,<4.0` on its own line, immediately after `python-dotenv>=1.0,<2.0`. Final file contents:

```
sqlalchemy>=2.0,<3.0
pandas>=2.0,<3.0
psycopg2-binary>=2.9,<3.0
pymysql>=1.1,<2.0
python-dotenv>=1.0,<2.0
snowflake-connector-python[pandas]>=3.0,<4.0
pytest>=8.0,<9.0
pytest-mock>=3.0,<4.0
```

Rationale for the `[pandas]` extra: `write_pandas` serializes the DataFrame to Parquet via `pyarrow` before PUTting it to an internal stage. The extra pulls in `pyarrow` (and `pyarrow`-compatible binaries) so the import works without a second install command.

- [ ] **Step 2: Activate venv and install**

Run:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Expected: pip resolves and installs `snowflake-connector-python`, `pyarrow`, `cryptography`, and their transitive deps. Exit code 0.

- [ ] **Step 3: Verify the package imports**

Run:

```bash
python -c "import snowflake.connector; from snowflake.connector.pandas_tools import write_pandas; print('ok')"
```

Expected output: `ok`

If this fails with `ModuleNotFoundError`, the `[pandas]` extra didn't land — re-run `pip install -r requirements.txt` and recheck.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "Add snowflake-connector-python[pandas] dependency"
```

---

## Task 2: Add `get_snowflake_connection()` to `pipeline/config.py`

**Files:**
- Modify: `pipeline/config.py` (append after the existing `get_rds_engine()` function)

- [ ] **Step 1: Append the connection factory**

Add this block to the bottom of `pipeline/config.py`:

```python
def get_snowflake_connection():
    import snowflake.connector

    kwargs = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "password": os.environ["SNOWFLAKE_PASSWORD"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "schema": os.environ.get("SNOWFLAKE_SCHEMA", "RAW"),
    }
    if role := os.environ.get("SNOWFLAKE_ROLE"):
        kwargs["role"] = role
    return snowflake.connector.connect(**kwargs)
```

Three deliberate choices in this function:

1. **Lazy import** of `snowflake.connector` inside the function body. `pipeline/config.py` is imported by every other path (MySQL extract, Postgres transform, RDS load, tests). The Snowflake connector has a heavy import chain (`pyarrow`, `cryptography`). Keeping the import lazy means unrelated paths aren't slowed by it and `pipeline/config.py` remains importable even when the Snowflake package isn't installed yet.
2. **Required vs optional env vars.** `account`, `user`, `password`, `warehouse`, `database` are accessed via `os.environ[key]` so a missing value raises `KeyError` immediately — the failure mode we want for a required credential. `schema` defaults to `"RAW"`. `role` is omitted entirely when unset so the Snowflake user's default role applies.
3. **Walrus operator** (`:= `) for the optional role keeps the "assign + truthy-check" tight and idiomatic in Python 3.8+.

- [ ] **Step 2: Verify the module still compiles**

Run:

```bash
python -m py_compile pipeline/config.py && echo OK
```

Expected output: `OK`

- [ ] **Step 3: Verify the lazy import doesn't fire at module load**

Run:

```bash
python -c "from pipeline.config import get_mysql_engine, get_snowflake_connection; print('imported without connecting')"
```

Expected output: `imported without connecting`

This confirms merely importing the helper does not attempt a Snowflake connection or import the connector. (The `snowflake.connector` import still executes on the first call to `get_snowflake_connection()`, which is the desired behavior.)

- [ ] **Step 4: Commit**

```bash
git add pipeline/config.py
git commit -m "Add get_snowflake_connection() helper to pipeline config"
```

---

## Task 3: Create `load_rds_to_snowflake.py`

**Files:**
- Create: `load_rds_to_snowflake.py` (top-level script, parallel to `load_raw_to_rds.py`)

- [ ] **Step 1: Write the script**

Create `load_rds_to_snowflake.py` with this exact content:

```python
#!/usr/bin/env python3
"""Copy every table from the RDS Postgres raw schema into Snowflake's raw schema."""
import logging
import os
import sys

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas
from sqlalchemy import inspect

from pipeline.config import get_rds_engine, get_snowflake_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

SOURCE_SCHEMA = "raw"
TARGET_SCHEMA = os.environ.get("SNOWFLAKE_SCHEMA", "RAW")


def ensure_target_schema(conn, schema):
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def copy_all_tables(rds_engine, sf_conn):
    tables = inspect(rds_engine).get_table_names(schema=SOURCE_SCHEMA)
    logger.info("Discovered %d tables in RDS %s schema: %s", len(tables), SOURCE_SCHEMA, tables)

    for table in tables:
        logger.info("Extracting %s.%s from RDS", SOURCE_SCHEMA, table)
        df = pd.read_sql_table(table, rds_engine, schema=SOURCE_SCHEMA)

        logger.info("Loading %s.%s into Snowflake (%d rows)", TARGET_SCHEMA, table, len(df))
        success, nchunks, nrows, _ = write_pandas(
            sf_conn,
            df,
            table_name=table.upper(),
            schema=TARGET_SCHEMA,
            auto_create_table=True,
            overwrite=True,
            quote_identifiers=False,
        )
        if not success:
            raise RuntimeError(f"write_pandas reported failure for table {table}")
        logger.info("Wrote %d rows across %d chunk(s) to %s.%s", nrows, nchunks, TARGET_SCHEMA, table.upper())

    logger.info("Done. Copied %d tables.", len(tables))


def main():
    rds_engine = get_rds_engine()
    sf_conn = get_snowflake_connection()
    try:
        ensure_target_schema(sf_conn, TARGET_SCHEMA)
        copy_all_tables(rds_engine, sf_conn)
    finally:
        sf_conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Snowflake raw load failed")
        sys.exit(1)
```

Design notes for the engineer:

- **Schema-aware reflection.** `inspect(rds_engine).get_table_names(schema="raw")` — Postgres has real schemas, so without `schema=` SQLAlchemy returns tables from `public` (empty in this project). The sibling MySQL loader (`load_raw_to_rds.py`) didn't need a `schema=` argument because MySQL's default "schema" is the database.
- **Uppercasing + `quote_identifiers=False`.** Belt-and-suspenders: the table name is uppercased in Python *and* `write_pandas` is told not to quote identifiers so columns also fold to uppercase on the Snowflake side. Result: tables land as `RAW.ORDERS`, queryable as `SELECT * FROM raw.orders` without double quotes. Skip either half and you'll end up with `raw."orders"` forever.
- **`auto_create_table=True, overwrite=True`.** `write_pandas` issues `CREATE OR REPLACE TABLE` before the `COPY INTO`. No destination DDL needs to pre-exist; every run is idempotent. Types are inferred from pandas dtypes — acceptable because this is a raw staging layer, not a curated model.
- **`try / finally` around the connection.** Snowflake connections hold a live session token and are not pooled. The SQLAlchemy RDS engine manages its own pool, so only the Snowflake connection needs an explicit close.
- **Checked return tuple.** `write_pandas` returns `(success, nchunks, nrows, output)`. We raise on `success=False` rather than silently continuing — a failed chunk upload must not look like success in the logs.

- [ ] **Step 2: Syntax-check the new script**

Run:

```bash
python -m py_compile load_rds_to_snowflake.py && echo OK
```

Expected output: `OK`

- [ ] **Step 3: Verify imports resolve**

Run:

```bash
python -c "import load_rds_to_snowflake; print('module loads')"
```

Expected output: `module loads`

This confirms all imports (`pandas`, `snowflake.connector.pandas_tools`, `sqlalchemy`, `pipeline.config`) resolve at load time without requiring actual DB connections.

- [ ] **Step 4: End-to-end manual smoke test**

Preconditions:

1. `.env` contains valid `RDS_*` and `SNOWFLAKE_*` values (see Task 4 for the full list).
2. `load_raw_to_rds.py` has run successfully against the current MySQL source, so RDS `raw.*` is populated.
3. The target Snowflake warehouse is resumed and the user has `CREATE SCHEMA` / `CREATE TABLE` privileges on `SNOWFLAKE_DATABASE`.

Run:

```bash
python load_rds_to_snowflake.py
```

Expected log lines (per table):

```
[INFO] __main__: Discovered N tables in RDS raw schema: [...]
[INFO] __main__: Extracting raw.<table> from RDS
[INFO] __main__: Loading RAW.<table> into Snowflake (<rowcount> rows)
[INFO] __main__: Wrote <rowcount> rows across <n> chunk(s) to RAW.<TABLE>
...
[INFO] __main__: Done. Copied N tables.
```

Final exit code: 0.

Verify in Snowflake:

```sql
USE DATABASE <SNOWFLAKE_DATABASE>;
USE SCHEMA RAW;
SHOW TABLES;
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) FROM order_items;
SELECT COUNT(*) FROM products;
```

Counts should match `SELECT COUNT(*) FROM raw.orders;` etc. on RDS.

- [ ] **Step 5: Re-run to confirm idempotency**

Run the script a second time with no other changes:

```bash
python load_rds_to_snowflake.py
```

Expected: same log output, same row counts. `CREATE OR REPLACE TABLE` under the hood means the second run drops and rebuilds each table — no duplicates, no stale columns from a prior schema.

- [ ] **Step 6: Commit**

```bash
git add load_rds_to_snowflake.py
git commit -m "Add RDS to Snowflake raw loader script"
```

---

## Task 4: Update `CLAUDE.md` with the new path

**Files:**
- Modify: `CLAUDE.md` — three separate edits: Commands block, Architecture section, Key Design Decisions bullets

- [ ] **Step 1: Add the new command**

Insert this block into the `## Commands` section, immediately after the `python load_raw_to_rds.py` command block:

```bash
# Copy the RDS raw schema into Snowflake's raw schema (no transforms)
python load_rds_to_snowflake.py
```

- [ ] **Step 2: Add the Snowflake architecture subsection**

Insert this subsection into the `## Architecture` section, immediately after the `### AWS RDS Raw Load` subsection (so the three paths — local, RDS, Snowflake — appear in order):

```markdown
### Snowflake Raw Load

A third destination copies the RDS raw layer into a Snowflake warehouse, again with no transformations. The script `load_rds_to_snowflake.py` runs separately from both `run_pipeline.py` and `load_raw_to_rds.py`. It uses SQLAlchemy's `inspect(engine).get_table_names(schema="raw")` against RDS to enumerate tables, reads each with `pandas.read_sql_table`, and writes it to Snowflake using `snowflake.connector.pandas_tools.write_pandas` with `overwrite=True` and `auto_create_table=True`. Under the hood `write_pandas` PUTs a Parquet file to an internal stage and issues `COPY INTO`, which is much faster than row-level inserts. Table and column names are uppercased and loaded with `quote_identifiers=False` to match Snowflake's native uppercase convention, so downstream queries use unquoted identifiers (`raw.orders`).

**Data flow (Snowflake variant)**: MySQL → RDS `raw.*` (via `load_raw_to_rds.py`) → Snowflake `raw.*` (via `load_rds_to_snowflake.py`)
```

- [ ] **Step 3: Expand the Key Design Decisions bullets**

Replace the bullet that begins with "`pipeline/config.py` exposes three engine factories..." with this expanded pair of bullets and add one more bullet below it about `write_pandas` idempotency:

```markdown
- `pipeline/config.py` exposes four connection factories: `get_mysql_engine()`, `get_postgres_engine()` (local Docker), `get_rds_engine()` (AWS RDS), and `get_snowflake_connection()` (Snowflake). The RDS helper reads `RDS_HOST`, `RDS_PORT`, `RDS_USER`, `RDS_PASSWORD`, and `RDS_DATABASE` from `.env`. The Snowflake helper reads `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, optional `SNOWFLAKE_SCHEMA` (default `RAW`), and optional `SNOWFLAKE_ROLE`.
- `get_snowflake_connection()` imports `snowflake.connector` lazily inside the function so `pipeline/config.py` stays importable when the Snowflake connector isn't installed — only the Snowflake loader path pays the dependency cost.
- The Snowflake raw-load uses `write_pandas(overwrite=True, auto_create_table=True)`, which issues a `CREATE OR REPLACE TABLE` and a `COPY INTO` per table. Destination DDL is not pre-created on Snowflake; types are inferred from pandas dtypes. This matches the RDS loader's idempotent drop-and-reload semantics.
```

- [ ] **Step 4: Verify the markdown renders and no sections were broken**

Run:

```bash
head -80 CLAUDE.md
```

Visually confirm:

1. The Commands block now contains four `python …` invocations in order: `run_pipeline.py`, `load_raw_to_rds.py`, `load_rds_to_snowflake.py`, `pytest …`.
2. The Architecture section contains three subsections in order: the default paragraph, `### AWS RDS Raw Load`, `### Snowflake Raw Load`.
3. The Key Design Decisions section contains a bullet naming `get_snowflake_connection()`.

If any of the three edits landed in the wrong spot (e.g., the new subsection appeared above AWS RDS Raw Load, or the command block got duplicated), fix in place and re-run the head check.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "Document RDS to Snowflake loader in CLAUDE.md"
```

---

## Task 5: End-to-end verification

**Files:** none modified in this task — purely verification.

- [ ] **Step 1: Clean run from a fresh shell**

In a new terminal:

```bash
cd /Users/greglontok/isba-4715/basket-craft-pipeline
source venv/bin/activate
python load_raw_to_rds.py
python load_rds_to_snowflake.py
```

Expected: both scripts exit 0. The second script discovers the same tables that the first wrote to RDS.

- [ ] **Step 2: Row-count parity check**

Row counts must match across MySQL → RDS → Snowflake for each table. Run each of these three commands and confirm the numeric output matches for each table in `SOURCE_SCHEMA`:

MySQL:

```bash
mysql -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" \
  -e "SELECT 'orders' AS t, COUNT(*) FROM orders UNION ALL SELECT 'order_items', COUNT(*) FROM order_items UNION ALL SELECT 'products', COUNT(*) FROM products;"
```

RDS:

```bash
PGPASSWORD="$RDS_PASSWORD" psql -h "$RDS_HOST" -U "$RDS_USER" -d "$RDS_DATABASE" \
  -c "SELECT 'orders' AS t, COUNT(*) FROM raw.orders UNION ALL SELECT 'order_items', COUNT(*) FROM raw.order_items UNION ALL SELECT 'products', COUNT(*) FROM raw.products;"
```

Snowflake (via the web UI or `snowsql`):

```sql
SELECT 'orders' AS t, COUNT(*) FROM RAW.ORDERS
UNION ALL SELECT 'order_items', COUNT(*) FROM RAW.ORDER_ITEMS
UNION ALL SELECT 'products', COUNT(*) FROM RAW.PRODUCTS;
```

Counts must agree across all three layers for every shared table.

- [ ] **Step 3: Final status check**

Run:

```bash
git status
git log --oneline -n 6
```

Expected: working tree clean, recent commits include the four commits from Tasks 1–4 in order. If anything is still uncommitted, return to the relevant task and finish the commit step.

---

## Self-Review

Ran fresh-eyes check against `docs/superpowers/specs/2026-04-20-rds-to-snowflake-loader-design.md`:

- **Spec coverage:**
  - Source auto-discovery via `inspect(...).get_table_names(schema="raw")` → Task 3 Step 1
  - Destination: `RAW` schema, uppercase identifiers, `quote_identifiers=False` → Task 3 Step 1
  - `write_pandas` connector choice + rationale → Task 3 Step 1 design notes
  - Connection lifecycle with `try/finally` + `sf_conn.close()` → Task 3 Step 1
  - `get_snowflake_connection()` signature, env vars, lazy import → Task 2
  - `requirements.txt` dependency with `[pandas]` extra → Task 1
  - `CLAUDE.md` command block, architecture subsection, design decisions → Task 4 (three explicit sub-steps)
  - Idempotency via `CREATE OR REPLACE TABLE` → Task 3 Step 5
  - `.env` variable list → Task 4 Step 3 (captured in the Key Design Decisions bullet rewrite)
  - Out-of-scope items (transforms in Snowflake, CDC, key-pair auth, parallel loads, drift validation) → not implemented, as specified

- **Placeholder scan:** no "TBD", "TODO", "implement later", "appropriate error handling", or "similar to Task N" strings. Every code block contains the complete code to paste. Every command has expected output.

- **Type/identifier consistency:** `get_snowflake_connection` is called the same way in Task 2 (definition), Task 3 Step 1 (import), and nowhere else. `TARGET_SCHEMA`, `SOURCE_SCHEMA`, `ensure_target_schema`, `copy_all_tables`, and `main` names match exactly across the script body, the design notes, and the verification steps. Env var names (`SNOWFLAKE_*`) match between Task 2 code, Task 4 doc bullet, and Task 5 verification commands.

No inline fixes needed — plan is ready.

---

## Execution Handoff

This plan is retroactive documentation: the implementation already landed in the working tree from the earlier out-of-process session. The recommended next action is not to re-execute Tasks 1–4 but to treat the plan as an audit trail. If future work re-implements this on a fresh branch, either subagent-driven-development or executing-plans can drive the task-by-task execution from the top.
