"""Add GIN index for full-text search and JSONB functional index for events.

Revision ID: 001_perf_indexes
Revises: 000_legacy
Create Date: 2026-06-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_perf_indexes"
down_revision = "000_legacy"
branch_labels = None
depends_on = None


def upgrade():
    # 1. GIN index for full-text search on news
    # Add a tsvector column and populate it, then create a GIN index
    op.execute("""
        ALTER TABLE news ADD COLUMN IF NOT EXISTS search_vector tsvector
    """)
    op.execute("""
        UPDATE news SET search_vector = 
            to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(translated_title, '') || ' ' || coalesce(content, ''))
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_search_vector ON news USING gin(search_vector)
    """)
    # Trigger to keep search_vector updated on INSERT/UPDATE
    op.execute("""
        CREATE OR REPLACE FUNCTION news_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple', 
                coalesce(NEW.title, '') || ' ' || coalesce(NEW.translated_title, '') || ' ' || coalesce(NEW.content, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS tsvector_update ON news
    """)
    op.execute("""
        CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE ON news
        FOR EACH ROW EXECUTE FUNCTION news_search_vector_update()
    """)

    # 2. JSONB functional index on events.data->>'event_type'
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_data_event_type ON events ((data->>'event_type'))
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS tsvector_update ON news")
    op.execute("DROP FUNCTION IF EXISTS news_search_vector_update()")
    op.drop_index("idx_news_search_vector", table_name="news")
    op.drop_column("news", "search_vector")
    op.drop_index("idx_events_data_event_type", table_name="events")
