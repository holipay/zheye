#!/usr/bin/env python3
"""
Backfill keywords and relations for existing news articles.
Run this once after deploying the keyword matching feature.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from models.base import async_session
from models.news import News
from scraper.pipeline.keywords import match_keywords, sync_keywords_to_db, save_article_keywords, load_keywords
from scraper.pipeline.relations import calculate_and_save_relations


async def backfill():
    keywords_data = load_keywords()
    print(f"Loaded {len(keywords_data)} keywords from lexicon")

    async with async_session() as session:
        term_to_id = await sync_keywords_to_db(session, keywords_data)
        await session.commit()
        print(f"Synced {len(term_to_id)} keywords to database")

    async with async_session() as session:
        result = await session.execute(select(News).order_by(News.id))
        articles = result.scalars().all()
        print(f"Found {len(articles)} articles to process")

        processed = 0
        total_matches = 0

        for article in articles:
            matched = match_keywords(
                title=article.title,
                translated_title=article.translated_title,
                summary=article.summary,
                category=article.category,
            )

            if matched:
                await save_article_keywords(session, article.id, matched, term_to_id)
                total_matches += len(matched)

            await calculate_and_save_relations(session, article.id, article.category)

            processed += 1
            if processed % 50 == 0:
                await session.commit()
                print(f"  Processed {processed}/{len(articles)} articles...")

        await session.commit()
        print(f"\nBackfill complete:")
        print(f"  Articles processed: {processed}")
        print(f"  Keyword matches: {total_matches}")


if __name__ == "__main__":
    asyncio.run(backfill())
