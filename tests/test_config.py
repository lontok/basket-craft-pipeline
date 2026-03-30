# tests/test_config.py
from pipeline.config import get_mysql_engine, get_postgres_engine


def test_get_mysql_engine_returns_engine():
    engine = get_mysql_engine()
    assert str(engine.url).startswith("mysql+pymysql://")


def test_get_postgres_engine_returns_engine():
    engine = get_postgres_engine()
    assert str(engine.url).startswith("postgresql+psycopg2://")
