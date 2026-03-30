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
