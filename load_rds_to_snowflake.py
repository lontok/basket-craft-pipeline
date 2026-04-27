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


def copy_all_tables(rds_engine, sf_conn):
    tables = inspect(rds_engine).get_table_names(schema=SOURCE_SCHEMA)
    logger.info("Discovered %d tables in RDS %s schema: %s", len(tables), SOURCE_SCHEMA, tables)

    for table in tables:
        logger.info("Extracting %s.%s from RDS", SOURCE_SCHEMA, table)
        df = pd.read_sql_table(table, rds_engine, schema=SOURCE_SCHEMA)
        df.columns = [c.upper() for c in df.columns]

        logger.info("Loading %s.%s into Snowflake (%d rows)", TARGET_SCHEMA, table, len(df))
        success, nchunks, nrows, _ = write_pandas(
            sf_conn,
            df,
            table_name=table.upper(),
            schema=TARGET_SCHEMA,
            auto_create_table=True,
            overwrite=True,
            quote_identifiers=False,
            use_logical_type=True,
        )
        if not success:
            raise RuntimeError(f"write_pandas reported failure for table {table}")
        logger.info("Wrote %d rows across %d chunk(s) to %s.%s", nrows, nchunks, TARGET_SCHEMA, table.upper())

    logger.info("Done. Copied %d tables.", len(tables))


def main():
    rds_engine = get_rds_engine()
    sf_conn = get_snowflake_connection()
    try:
        copy_all_tables(rds_engine, sf_conn)
    finally:
        sf_conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Snowflake raw load failed")
        sys.exit(1)
