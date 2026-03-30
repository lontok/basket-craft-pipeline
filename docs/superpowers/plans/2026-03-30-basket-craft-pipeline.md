# Basket Craft Sales Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an ELT pipeline that extracts sales data from a MySQL database, loads it into a local Dockerized Postgres, and transforms it into a monthly sales summary table.

**Architecture:** Python extracts 3 tables (`orders`, `order_items`, `products`) from MySQL into a Postgres `raw` schema. A SQL query then aggregates that raw data into `analytics.monthly_sales_summary` with revenue, order counts, and average order value by product and month. Each run is idempotent (truncate + reload).

**Tech Stack:** Python 3, SQLAlchemy, pandas, psycopg2, pymysql, python-dotenv, Docker Compose (Postgres 16), pytest

---

## File Map

| File | Responsibility |
|------|---------------|
| `docker-compose.yml` | Postgres 16 container with persistent volume |
| `requirements.txt` | Python dependencies |
| `.env` | MySQL + Postgres credentials (already exists with MySQL creds) |
| `pipeline/__init__.py` | Package marker |
| `pipeline/config.py` | Reads `.env`, builds SQLAlchemy engine objects |
| `pipeline/extract.py` | Reads MySQL tables, writes to Postgres `raw` schema |
| `pipeline/transform.py` | Runs SQL transform from `raw` to `analytics` |
| `sql/create_schemas.sql` | DDL: creates `raw` and `analytics` schemas + tables |
| `sql/monthly_summary.sql` | Transform query: aggregates into `monthly_sales_summary` |
| `run_pipeline.py` | CLI entry point — orchestrates extract → transform |
| `tests/conftest.py` | Pytest fixtures: Postgres connection, schema setup/teardown |
| `tests/test_transform.py` | Tests the SQL transform logic against fixture data |
| `tests/test_extract.py` | Tests schema drift detection |

---

### Task 1: Docker Compose and Python Environment

**Files:**
- Create: `docker-compose.yml`
- Create: `requirements.txt`
- Modify: `.env`

- [ ] **Step 1: Add Postgres credentials to `.env`**

Append these lines to the existing `.env` file:

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=pipeline
POSTGRES_PASSWORD=pipeline_pass
POSTGRES_DB=basket_craft_dw
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    container_name: basket_craft_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "${POSTGRES_PORT}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

- [ ] **Step 3: Create `requirements.txt`**

```
sqlalchemy>=2.0,<3.0
pandas>=2.0,<3.0
psycopg2-binary>=2.9,<3.0
pymysql>=1.1,<2.0
python-dotenv>=1.0,<2.0
pytest>=8.0,<9.0
```

- [ ] **Step 4: Start Postgres and set up Python venv**

```bash
docker compose up -d
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 5: Verify Postgres is running**

```bash
docker compose ps
```

Expected: `basket_craft_postgres` with status `running`, port `5432->5432/tcp`.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml requirements.txt .env
git commit -m "Add Docker Compose for Postgres and Python dependencies"
```

> **Note:** Committing `.env` here for project bootstrapping. In a production setting, `.env` would be in `.gitignore` and distributed separately.

---

### Task 2: Database Configuration Module

**Files:**
- Create: `pipeline/__init__.py`
- Create: `pipeline/config.py`

- [ ] **Step 1: Create package marker**

```python
# pipeline/__init__.py
```

(Empty file — just marks the directory as a Python package.)

- [ ] **Step 2: Write the failing test for config**

Create `tests/__init__.py` (empty) and `tests/test_config.py`:

```python
# tests/test_config.py
from pipeline.config import get_mysql_engine, get_postgres_engine


def test_get_mysql_engine_returns_engine():
    engine = get_mysql_engine()
    assert str(engine.url).startswith("mysql+pymysql://")


def test_get_postgres_engine_returns_engine():
    engine = get_postgres_engine()
    assert str(engine.url).startswith("postgresql+psycopg2://")
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'pipeline.config'`

- [ ] **Step 4: Write `pipeline/config.py`**

```python
# pipeline/config.py
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()


def get_mysql_engine():
    url = (
        f"mysql+pymysql://{os.environ['MYSQL_USER']}:{os.environ['MYSQL_PASSWORD']}"
        f"@{os.environ['MYSQL_HOST']}:{os.environ['MYSQL_PORT']}"
        f"/{os.environ['MYSQL_DATABASE']}"
    )
    return create_engine(url)


def get_postgres_engine():
    url = (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
        f"/{os.environ['POSTGRES_DB']}"
    )
    return create_engine(url)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/ tests/
git commit -m "Add database configuration module with MySQL and Postgres engines"
```

---

### Task 3: SQL Schema DDL

**Files:**
- Create: `sql/create_schemas.sql`

- [ ] **Step 1: Create `sql/create_schemas.sql`**

This SQL creates the `raw` and `analytics` schemas and their tables in Postgres. It uses `IF NOT EXISTS` so it's safe to re-run.

```sql
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
```

- [ ] **Step 2: Run the DDL against Postgres to verify it works**

```bash
PGPASSWORD=pipeline_pass psql -h localhost -U pipeline -d basket_craft_dw -f sql/create_schemas.sql
```

Expected: `CREATE SCHEMA` / `CREATE TABLE` messages with no errors.

- [ ] **Step 3: Verify schemas exist**

```bash
PGPASSWORD=pipeline_pass psql -h localhost -U pipeline -d basket_craft_dw -c "\dn"
```

Expected: `analytics`, `public`, and `raw` schemas listed.

- [ ] **Step 4: Commit**

```bash
git add sql/
git commit -m "Add SQL DDL for raw and analytics schemas"
```

---

### Task 4: Extract Module

**Files:**
- Create: `pipeline/extract.py`
- Create: `tests/test_extract.py`

- [ ] **Step 1: Write the failing test for schema validation**

```python
# tests/test_extract.py
from pipeline.extract import EXPECTED_COLUMNS, validate_source_schema


def test_validate_source_schema_passes_with_valid_columns(mocker):
    """Validate passes when all expected columns are present."""
    mock_engine = mocker.MagicMock()
    mock_inspector = mocker.patch("pipeline.extract.inspect")
    mock_inspector.return_value.get_columns.return_value = [
        {"name": col} for col in EXPECTED_COLUMNS["orders"]
    ]
    # Should not raise
    validate_source_schema(mock_engine, "orders")


def test_validate_source_schema_fails_with_missing_columns(mocker):
    """Validate raises when expected columns are missing."""
    import pytest

    mock_engine = mocker.MagicMock()
    mock_inspector = mocker.patch("pipeline.extract.inspect")
    mock_inspector.return_value.get_columns.return_value = [
        {"name": "order_id"}
    ]
    with pytest.raises(ValueError, match="Missing columns"):
        validate_source_schema(mock_engine, "orders")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pip install pytest-mock
pytest tests/test_extract.py -v
```

Expected: `ModuleNotFoundError: No module named 'pipeline.extract'`

- [ ] **Step 3: Write `pipeline/extract.py`**

```python
# pipeline/extract.py
import logging

import pandas as pd
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

SOURCE_TABLES = ["orders", "order_items", "products"]

EXPECTED_COLUMNS = {
    "orders": [
        "order_id", "created_at", "website_session_id", "user_id",
        "primary_product_id", "items_purchased", "price_usd", "cogs_usd",
    ],
    "order_items": [
        "order_item_id", "created_at", "order_id", "product_id",
        "is_primary_item", "price_usd", "cogs_usd",
    ],
    "products": [
        "product_id", "created_at", "product_name", "description",
    ],
}


def validate_source_schema(engine, table_name):
    """Check that expected columns exist in the source table."""
    inspector = inspect(engine)
    actual_columns = {col["name"] for col in inspector.get_columns(table_name)}
    expected = set(EXPECTED_COLUMNS[table_name])
    missing = expected - actual_columns
    if missing:
        raise ValueError(
            f"Missing columns in {table_name}: {missing}. "
            "Source schema may have changed."
        )


def extract_and_load(mysql_engine, pg_engine):
    """Extract tables from MySQL and load into Postgres raw schema."""
    for table in SOURCE_TABLES:
        logger.info("Validating schema for %s", table)
        validate_source_schema(mysql_engine, table)

        logger.info("Extracting %s from MySQL", table)
        df = pd.read_sql_table(table, mysql_engine)

        logger.info("Loading %s into raw schema (%d rows)", table, len(df))
        with pg_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE raw.{table}"))
        df.to_sql(table, pg_engine, schema="raw", if_exists="append", index=False)

    logger.info("Extraction complete")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_extract.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/extract.py tests/test_extract.py
git commit -m "Add extract module with schema validation"
```

---

### Task 5: Transform SQL and Module

**Files:**
- Create: `sql/monthly_summary.sql`
- Create: `pipeline/transform.py`
- Create: `tests/test_transform.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `sql/monthly_summary.sql`**

```sql
-- Truncate and rebuild the monthly sales summary from raw data.
TRUNCATE TABLE analytics.monthly_sales_summary;

INSERT INTO analytics.monthly_sales_summary
    (month, product_name, total_revenue, order_count, avg_order_value, total_items_sold, loaded_at)
SELECT
    DATE_TRUNC('month', oi.created_at)::DATE AS month,
    p.product_name,
    SUM(oi.price_usd)                        AS total_revenue,
    COUNT(DISTINCT oi.order_id)              AS order_count,
    ROUND(SUM(oi.price_usd) / COUNT(DISTINCT oi.order_id), 2) AS avg_order_value,
    COUNT(*)                                  AS total_items_sold,
    NOW()                                     AS loaded_at
FROM raw.order_items oi
JOIN raw.products p ON oi.product_id = p.product_id
GROUP BY DATE_TRUNC('month', oi.created_at)::DATE, p.product_name
ORDER BY month, product_name;
```

- [ ] **Step 2: Write `pipeline/transform.py`**

```python
# pipeline/transform.py
import logging
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def run_transform(pg_engine):
    """Execute the monthly summary transform SQL against Postgres."""
    sql_path = SQL_DIR / "monthly_summary.sql"
    sql = sql_path.read_text()

    logger.info("Running transform: %s", sql_path.name)
    with pg_engine.begin() as conn:
        conn.execute(text(sql))
    logger.info("Transform complete")
```

- [ ] **Step 3: Write `tests/conftest.py` with Postgres fixtures**

```python
# tests/conftest.py
import pytest
from sqlalchemy import text

from pipeline.config import get_postgres_engine


@pytest.fixture(scope="session")
def pg_engine():
    """Postgres engine pointing at the Docker container."""
    engine = get_postgres_engine()
    # Create schemas and tables
    ddl_path = "sql/create_schemas.sql"
    with open(ddl_path) as f:
        ddl = f.read()
    with engine.begin() as conn:
        for statement in ddl.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
    yield engine


@pytest.fixture
def seed_raw_data(pg_engine):
    """Insert a small fixture dataset into raw tables, clean up after."""
    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE raw.products, raw.order_items, raw.orders"))

        conn.execute(text("""
            INSERT INTO raw.products (product_id, created_at, product_name)
            VALUES
                (1, '2023-03-19', 'The Original Gift Basket'),
                (2, '2024-01-06', 'The Valentine''s Gift Basket')
        """))

        conn.execute(text("""
            INSERT INTO raw.orders (order_id, created_at, items_purchased, price_usd, cogs_usd)
            VALUES
                (1, '2024-01-15 10:00:00', 1, 49.99, 20.00),
                (2, '2024-01-20 11:00:00', 1, 64.99, 25.00),
                (3, '2024-02-10 09:00:00', 1, 49.99, 20.00)
        """))

        conn.execute(text("""
            INSERT INTO raw.order_items (order_item_id, created_at, order_id, product_id, is_primary_item, price_usd, cogs_usd)
            VALUES
                (1, '2024-01-15 10:00:00', 1, 1, 1, 49.99, 20.00),
                (2, '2024-01-20 11:00:00', 2, 2, 1, 64.99, 25.00),
                (3, '2024-02-10 09:00:00', 3, 1, 1, 49.99, 20.00)
        """))

    yield

    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE analytics.monthly_sales_summary"))
        conn.execute(text("TRUNCATE TABLE raw.products, raw.order_items, raw.orders"))
```

- [ ] **Step 4: Write `tests/test_transform.py`**

```python
# tests/test_transform.py
from decimal import Decimal

from sqlalchemy import text

from pipeline.transform import run_transform


def test_monthly_summary_aggregates_correctly(pg_engine, seed_raw_data):
    """Verify the transform produces correct aggregations from fixture data."""
    run_transform(pg_engine)

    with pg_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM analytics.monthly_sales_summary ORDER BY month, product_name")
        ).mappings().all()

    assert len(rows) == 3

    # Jan 2024, Original Gift Basket: 1 order, $49.99
    jan_original = rows[0]
    assert jan_original["product_name"] == "The Original Gift Basket"
    assert jan_original["month"].strftime("%Y-%m") == "2024-01"
    assert jan_original["total_revenue"] == Decimal("49.99")
    assert jan_original["order_count"] == 1
    assert jan_original["avg_order_value"] == Decimal("49.99")
    assert jan_original["total_items_sold"] == 1

    # Jan 2024, Valentine's Gift Basket: 1 order, $64.99
    jan_valentine = rows[1]
    assert jan_valentine["product_name"] == "The Valentine's Gift Basket"
    assert jan_valentine["total_revenue"] == Decimal("64.99")
    assert jan_valentine["order_count"] == 1

    # Feb 2024, Original Gift Basket: 1 order, $49.99
    feb_original = rows[2]
    assert feb_original["month"].strftime("%Y-%m") == "2024-02"
    assert feb_original["total_revenue"] == Decimal("49.99")


def test_transform_is_idempotent(pg_engine, seed_raw_data):
    """Running transform twice should produce the same result (truncate + reload)."""
    run_transform(pg_engine)
    run_transform(pg_engine)

    with pg_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM analytics.monthly_sales_summary")
        ).scalar()

    assert count == 3
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_transform.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add sql/monthly_summary.sql pipeline/transform.py tests/conftest.py tests/test_transform.py
git commit -m "Add transform module with monthly summary SQL and tests"
```

---

### Task 6: Pipeline Entry Point

**Files:**
- Create: `run_pipeline.py`

- [ ] **Step 1: Write `run_pipeline.py`**

```python
#!/usr/bin/env python3
# run_pipeline.py
import logging
import sys

from sqlalchemy import text

from pipeline.config import get_mysql_engine, get_postgres_engine
from pipeline.extract import extract_and_load
from pipeline.transform import run_transform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def init_schemas(pg_engine):
    """Run the DDL to create schemas and tables if they don't exist."""
    with open("sql/create_schemas.sql") as f:
        ddl = f.read()
    with pg_engine.begin() as conn:
        for statement in ddl.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))


def main():
    logger.info("Starting Basket Craft pipeline")

    mysql_engine = get_mysql_engine()
    pg_engine = get_postgres_engine()

    logger.info("Initializing Postgres schemas")
    init_schemas(pg_engine)

    logger.info("Step 1/2: Extract and load")
    extract_and_load(mysql_engine, pg_engine)

    logger.info("Step 2/2: Transform")
    run_transform(pg_engine)

    logger.info("Pipeline complete")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
```

- [ ] **Step 2: Run the full pipeline end-to-end**

```bash
python run_pipeline.py
```

Expected: Log output showing extraction of 3 tables, then transform, ending with "Pipeline complete".

- [ ] **Step 3: Verify data landed in Postgres**

```bash
PGPASSWORD=pipeline_pass psql -h localhost -U pipeline -d basket_craft_dw -c \
  "SELECT month, product_name, total_revenue, order_count, avg_order_value, total_items_sold FROM analytics.monthly_sales_summary ORDER BY month DESC, product_name LIMIT 10;"
```

Expected: Rows showing monthly aggregations by product with revenue, counts, and averages.

- [ ] **Step 4: Commit**

```bash
git add run_pipeline.py
git commit -m "Add pipeline entry point"
```

---

### Task 7: Run Full Test Suite and Final Verification

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass (config tests, extract schema validation tests, transform tests).

- [ ] **Step 2: Run pipeline a second time to verify idempotency**

```bash
python run_pipeline.py
```

Then check the row count hasn't doubled:

```bash
PGPASSWORD=pipeline_pass psql -h localhost -U pipeline -d basket_craft_dw -c \
  "SELECT COUNT(*) FROM analytics.monthly_sales_summary;"
```

Expected: Same count as the first run (one row per product per month).

- [ ] **Step 3: Commit any remaining changes**

```bash
git status
```

If clean, no commit needed. If there are unstaged files (e.g., `tests/__init__.py`), stage and commit:

```bash
git add -A
git commit -m "Final cleanup: ensure all test files are tracked"
```
