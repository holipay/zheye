#!/usr/bin/env python3
"""Stamp the database with the 'base' revision.

Usage:
    DATABASE_URL=postgresql+asyncpg://user:pass@host/db python scripts/stamp_migrations.py

This marks the database as having all legacy schema (migrations 001-018) applied,
so future Alembic migrations can build on top.
"""

import os
import asyncio
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def stamp():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        # Create alembic_version table if not exists
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
        """))

        # Clear any existing version
        await conn.execute(text("DELETE FROM alembic_version"))

        # Stamp with the legacy base revision
        await conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
            {"v": "000_legacy"},
        )
        print("Stamped alembic_version with: 000_legacy")
        print("All 18 legacy SQL migrations (001-018) marked as applied.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(stamp())
