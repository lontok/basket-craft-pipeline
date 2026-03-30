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
