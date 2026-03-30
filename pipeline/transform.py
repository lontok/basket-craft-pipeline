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
