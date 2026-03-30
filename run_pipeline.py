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
