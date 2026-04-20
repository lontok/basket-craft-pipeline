#!/usr/bin/env python3
"""Extract every table from the MySQL source and load it as-is into RDS Postgres."""
import logging
import sys

import pandas as pd
from sqlalchemy import inspect, text

from pipeline.config import get_mysql_engine, get_rds_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RAW_SCHEMA = "raw"


def ensure_raw_schema(pg_engine):
    with pg_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}"))


def copy_all_tables(mysql_engine, pg_engine):
    tables = inspect(mysql_engine).get_table_names()
    logger.info("Discovered %d tables in MySQL: %s", len(tables), tables)

    for table in tables:
        logger.info("Extracting %s from MySQL", table)
        df = pd.read_sql_table(table, mysql_engine)

        logger.info("Loading %s into %s.%s (%d rows)", table, RAW_SCHEMA, table, len(df))
        df.to_sql(
            table,
            pg_engine,
            schema=RAW_SCHEMA,
            if_exists="replace",
            index=False,
        )

    logger.info("Done. Copied %d tables.", len(tables))


def main():
    mysql_engine = get_mysql_engine()
    rds_engine = get_rds_engine()

    ensure_raw_schema(rds_engine)
    copy_all_tables(mysql_engine, rds_engine)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Raw load failed")
        sys.exit(1)
