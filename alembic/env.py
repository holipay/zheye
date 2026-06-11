import os
import sys
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models.base import Base

# Import all core models so Base.metadata knows about them
from models.news import News  # noqa: F401
from models.analysis import Analysis  # noqa: F401
from models.translation_cache import TranslationCache  # noqa: F401
from models.source_health import SourceHealth  # noqa: F401
from models.run_metrics import RunMetrics  # noqa: F401
from models.keyword import Keyword  # noqa: F401
from models.article_keyword import ArticleKeyword  # noqa: F401
from models.article_relation import ArticleRelation  # noqa: F401
from models.entity import Entity  # noqa: F401
from models.article_entity import ArticleEntity  # noqa: F401
from models.daily_report import DailyReport  # noqa: F401
from models.trend import Trend  # noqa: F401
from models.event import Event  # noqa: F401
from models.market_data import MarketData  # noqa: F401
from models.analysis_version import AnalysisVersion  # noqa: F401
from models.failed_task import FailedAnalysisTask  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from environment variable
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
