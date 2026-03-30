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
