from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import date, datetime
from sqlalchemy import select, func, desc, case, text
from models.base import async_session
from models.news import News
from models.keyword import Keyword
from models.article_keyword import ArticleKeyword
from models.article_relation import ArticleRelation
from models.entity import Entity
from models.article_entity import ArticleEntity

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/news", response_class=HTMLResponse)
async def get_news(
    request: Request,
    category: str = "all",
    article_type: str = "all",
    keyword_id: int = None,
    sort: str = "date",
    page: int = 1,
):
    page_size = 20
    offset = (page - 1) * page_size

    async with async_session() as session:
        if sort == "weight":
            weight_sum = func.coalesce(func.sum(Keyword.weight), 0).label("total_weight")

            base_query = (
                select(News, weight_sum)
                .outerjoin(ArticleKeyword, ArticleKeyword.article_id == News.id)
                .outerjoin(Keyword, Keyword.id == ArticleKeyword.keyword_id)
                .group_by(News.id)
            )

            count_query = select(func.count(func.distinct(News.id)))
            if keyword_id:
                base_query = base_query.having(func.count(ArticleKeyword.id) > 0)
                count_query = (
                    select(func.count(func.distinct(News.id)))
                    .select_from(News)
                    .join(ArticleKeyword, ArticleKeyword.article_id == News.id)
                    .where(ArticleKeyword.keyword_id == keyword_id)
                )

            if category and category != "all":
                base_query = base_query.where(News.category == category)
                count_query = count_query.where(News.category == category)
            if article_type and article_type != "all":
                base_query = base_query.where(News.article_type == article_type)
                count_query = count_query.where(News.article_type == article_type)
            if keyword_id:
                base_query = base_query.where(ArticleKeyword.keyword_id == keyword_id)

            total_result = await session.execute(count_query)
            total = total_result.scalar()

            query = base_query.order_by(desc("total_weight"), desc(News.date)).offset(offset).limit(page_size)
            result = await session.execute(query)
            rows = result.all()
            news_items = []
            for news, weight in rows:
                news._weight = weight
                news_items.append(news)
        else:
            query = select(News).order_by(desc(News.date))
            count_query = select(func.count(News.id))

            if category and category != "all":
                query = query.where(News.category == category)
                count_query = count_query.where(News.category == category)
            if article_type and article_type != "all":
                query = query.where(News.article_type == article_type)
                count_query = count_query.where(News.article_type == article_type)
            if keyword_id:
                query = (
                    query.join(ArticleKeyword, ArticleKeyword.article_id == News.id)
                    .where(ArticleKeyword.keyword_id == keyword_id)
                )
                count_query = (
                    count_query.select_from(News)
                    .join(ArticleKeyword, ArticleKeyword.article_id == News.id)
                    .where(ArticleKeyword.keyword_id == keyword_id)
                )

            total_result = await session.execute(count_query)
            total = total_result.scalar()

            query = query.offset(offset).limit(page_size)
            result = await session.execute(query)
            news_items = result.scalars().all()

        total_pages = (total + page_size - 1) // page_size

    return templates.TemplateResponse(request=request, name="partials/news_list.html", context={
        "news_items": news_items,
        "category": category,
        "article_type": article_type,
        "keyword_id": keyword_id,
        "sort": sort,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.get("/categories", response_class=HTMLResponse)
async def get_categories(request: Request):
    async with async_session() as session:
        query = select(News.category, func.count(News.id)).group_by(News.category).order_by(desc(func.count(News.id)))
        result = await session.execute(query)
        categories = result.all()
    
    return templates.TemplateResponse(request=request, name="partials/categories.html", context={
        "categories": categories,
    })


@router.get("/article-types", response_class=HTMLResponse)
async def get_article_types(request: Request):
    async with async_session() as session:
        query = select(News.article_type, func.count(News.id)).group_by(News.article_type).order_by(desc(func.count(News.id)))
        result = await session.execute(query)
        article_types = result.all()
    
    return templates.TemplateResponse(request=request, name="partials/article_types.html", context={
        "article_types": article_types,
    })


@router.get("/latest", response_class=HTMLResponse)
async def get_latest(request: Request, limit: int = 10):
    async with async_session() as session:
        query = select(News).order_by(desc(News.created_at)).limit(limit)
        result = await session.execute(query)
        news_items = result.scalars().all()
    
    return templates.TemplateResponse(request=request, name="partials/news_list.html", context={
        "news_items": news_items,
        "category": "all",
        "page": 1,
        "total_pages": 1,
        "total": len(news_items),
    })


@router.get("/meta")
async def get_meta():
    async with async_session() as session:
        count_result = await session.execute(select(func.count(News.id)))
        total = count_result.scalar()
        
        source_query = select(News.source, func.count(News.id)).group_by(News.source).order_by(desc(func.count(News.id)))
        source_result = await session.execute(source_query)
        sources = [{"name": row[0], "count": row[1]} for row in source_result.all()]
        
        category_query = select(News.category, func.count(News.id)).group_by(News.category).order_by(desc(func.count(News.id)))
        category_result = await session.execute(category_query)
        categories = [{"name": row[0], "count": row[1]} for row in category_result.all()]
    
    return {
        "total": total,
        "sources": sources,
        "categories": categories,
    }


@router.get("/news/{news_id}/related")
async def get_related_news(news_id: int, limit: int = 10):
    async with async_session() as session:
        news_result = await session.execute(select(News).where(News.id == news_id))
        news = news_result.scalar_one_or_none()
        if not news:
            raise HTTPException(status_code=404, detail="News not found")

        query = (
            select(News, ArticleRelation.score)
            .join(ArticleRelation, ArticleRelation.target_id == News.id)
            .where(ArticleRelation.source_id == news_id)
            .order_by(desc(ArticleRelation.score))
            .limit(limit)
        )
        result = await session.execute(query)
        rows = result.all()

        related = []
        for news_item, score in rows:
            related.append({
                "id": news_item.id,
                "title": news_item.title,
                "translated_title": news_item.translated_title,
                "link": news_item.link,
                "source": news_item.source,
                "category": news_item.category,
                "date": news_item.date.isoformat() if news_item.date else None,
                "score": score,
            })

    return {"news_id": news_id, "related": related}


@router.get("/keywords")
async def get_keywords(category: str = None, lang: str = None, page: int = 1, page_size: int = 50):
    async with async_session() as session:
        query = select(Keyword)
        count_query = select(func.count(Keyword.id))

        if category:
            query = query.where(Keyword.category == category)
            count_query = count_query.where(Keyword.category == category)
        if lang:
            query = query.where(Keyword.lang == lang)
            count_query = count_query.where(Keyword.lang == lang)

        total_result = await session.execute(count_query)
        total = total_result.scalar()

        offset = (page - 1) * page_size
        query = query.order_by(Keyword.category, desc(Keyword.weight)).offset(offset).limit(page_size)
        result = await session.execute(query)
        keywords = result.scalars().all()

        keyword_list = []
        for kw in keywords:
            count_result = await session.execute(
                select(func.count(ArticleKeyword.id)).where(ArticleKeyword.keyword_id == kw.id)
            )
            article_count = count_result.scalar()

            keyword_list.append({
                "id": kw.id,
                "term": kw.term,
                "lang": kw.lang,
                "category": kw.category,
                "weight": kw.weight,
                "article_count": article_count,
            })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "keywords": keyword_list,
    }


@router.get("/keywords/popular", response_class=HTMLResponse)
async def get_popular_keywords(request: Request, limit: int = 20):
    async with async_session() as session:
        query = (
            select(Keyword, func.count(ArticleKeyword.id).label("article_count"))
            .outerjoin(ArticleKeyword, ArticleKeyword.keyword_id == Keyword.id)
            .group_by(Keyword.id)
            .having(func.count(ArticleKeyword.id) > 0)
            .order_by(desc(func.count(ArticleKeyword.id)))
            .limit(limit)
        )
        result = await session.execute(query)
        rows = result.all()

        keywords = []
        for kw, count in rows:
            keywords.append({
                "id": kw.id,
                "term": kw.term,
                "category": kw.category,
                "article_count": count,
            })

    return templates.TemplateResponse(request=request, name="partials/keywords.html", context={
        "keywords": keywords,
    })


@router.get("/keywords/{keyword_id}/articles")
async def get_articles_by_keyword(keyword_id: int, page: int = 1, page_size: int = 20):
    async with async_session() as session:
        kw_result = await session.execute(select(Keyword).where(Keyword.id == keyword_id))
        keyword = kw_result.scalar_one_or_none()
        if not keyword:
            raise HTTPException(status_code=404, detail="Keyword not found")

        count_query = select(func.count(ArticleKeyword.id)).where(ArticleKeyword.keyword_id == keyword_id)
        total_result = await session.execute(count_query)
        total = total_result.scalar()

        offset = (page - 1) * page_size
        query = (
            select(News)
            .join(ArticleKeyword, ArticleKeyword.article_id == News.id)
            .where(ArticleKeyword.keyword_id == keyword_id)
            .order_by(desc(News.date))
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(query)
        news_items = result.scalars().all()

        articles = []
        for item in news_items:
            articles.append({
                "id": item.id,
                "title": item.title,
                "translated_title": item.translated_title,
                "link": item.link,
                "source": item.source,
                "category": item.category,
                "date": item.date.isoformat() if item.date else None,
            })

    return {
        "keyword": {
            "id": keyword.id,
            "term": keyword.term,
            "lang": keyword.lang,
            "category": keyword.category,
        },
        "total": total,
        "page": page,
        "page_size": page_size,
        "articles": articles,
    }


@router.get("/news/{news_id}", response_class=HTMLResponse)
async def get_news_detail(request: Request, news_id: int):
    async with async_session() as session:
        news_result = await session.execute(select(News).where(News.id == news_id))
        news = news_result.scalar_one_or_none()
        if not news:
            raise HTTPException(status_code=404, detail="News not found")

        keywords_query = (
            select(Keyword)
            .join(ArticleKeyword, ArticleKeyword.keyword_id == Keyword.id)
            .where(ArticleKeyword.article_id == news_id)
            .order_by(desc(Keyword.weight))
        )
        keywords_result = await session.execute(keywords_query)
        keywords = keywords_result.scalars().all()

        entities_query = (
            select(Entity, ArticleEntity.context)
            .join(ArticleEntity, ArticleEntity.entity_id == Entity.id)
            .where(ArticleEntity.article_id == news_id)
            .order_by(Entity.entity_type, Entity.name)
        )
        entities_result = await session.execute(entities_query)
        entities = [
            {
                "name": entity.name,
                "entity_type": entity.entity_type,
                "context": context,
            }
            for entity, context in entities_result.all()
        ]

        related_query = (
            select(News, ArticleRelation.score, ArticleRelation.relation_type)
            .join(ArticleRelation, ArticleRelation.target_id == News.id)
            .where(ArticleRelation.source_id == news_id)
            .order_by(desc(ArticleRelation.score))
            .limit(10)
        )
        related_result = await session.execute(related_query)
        related = [
            {
                "id": r.id,
                "title": r.title,
                "translated_title": r.translated_title,
                "source": r.source,
                "category": r.category,
                "date": r.date.strftime("%Y-%m-%d") if r.date else None,
                "score": score,
                "relation_type": relation_type,
            }
            for r, score, relation_type in related_result.all()
        ]

    return templates.TemplateResponse(request=request, name="partials/news_detail.html", context={
        "news": news,
        "keywords": keywords,
        "entities": entities,
        "related": related,
    })


@router.get("/entities/popular", response_class=HTMLResponse)
async def get_popular_entities(request: Request, entity_type: str = None, limit: int = 15):
    async with async_session() as session:
        query = (
            select(Entity, func.count(ArticleEntity.id).label("article_count"))
            .join(ArticleEntity, ArticleEntity.entity_id == Entity.id)
            .group_by(Entity.id)
            .having(func.count(ArticleEntity.id) > 0)
        )

        if entity_type:
            query = query.where(Entity.entity_type == entity_type)

        query = query.order_by(desc(func.count(ArticleEntity.id))).limit(limit)
        result = await session.execute(query)
        rows = result.all()

        entities = []
        for ent, count in rows:
            entities.append({
                "id": ent.id,
                "name": ent.name,
                "entity_type": ent.entity_type,
                "article_count": count,
            })

    return templates.TemplateResponse(request=request, name="partials/entity_list.html", context={
        "entities": entities,
        "entity_type": entity_type,
    })


@router.get("/entities/types", response_class=HTMLResponse)
async def get_entity_types(request: Request):
    async with async_session() as session:
        query = (
            select(Entity.entity_type, func.count(Entity.id))
            .group_by(Entity.entity_type)
            .order_by(desc(func.count(Entity.id)))
        )
        result = await session.execute(query)
        types = result.all()

    return templates.TemplateResponse(request=request, name="partials/entity_types.html", context={
        "types": types,
    })


@router.get("/news/by-entity/{entity_id}", response_class=HTMLResponse)
async def get_news_by_entity(request: Request, entity_id: int, page: int = 1, page_size: int = 20):
    async with async_session() as session:
        ent_result = await session.execute(select(Entity).where(Entity.id == entity_id))
        entity = ent_result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        count_query = select(func.count(ArticleEntity.id)).where(ArticleEntity.entity_id == entity_id)
        total_result = await session.execute(count_query)
        total = total_result.scalar()

        offset = (page - 1) * page_size
        query = (
            select(News)
            .join(ArticleEntity, ArticleEntity.article_id == News.id)
            .where(ArticleEntity.entity_id == entity_id)
            .order_by(desc(News.date))
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(query)
        news_items = result.scalars().all()

        total_pages = (total + page_size - 1) // page_size

    return templates.TemplateResponse(request=request, name="partials/news_list.html", context={
        "news_items": news_items,
        "category": "all",
        "article_type": "all",
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


# ============================================================
# AI 分析相关 API
# ============================================================

@router.get("/analysis/daily/{target_date}")
async def get_daily_report(target_date: str):
    """获取每日分析报告"""
    try:
        report_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")
    
    async with async_session() as session:
        # 查询每日报告
        stmt = text("""
            SELECT date, overview, hot_topics, market_sentiment, key_events, 
                   trend_analysis, news_count, generated_at
            FROM daily_reports
            WHERE date = :report_date
        """)
        result = await session.execute(stmt, {"report_date": report_date})
        report = result.mappings().first()
        
        if not report:
            raise HTTPException(status_code=404, detail=f"未找到 {target_date} 的分析报告")
        
        return {
            "date": str(report["date"]),
            "overview": report["overview"],
            "hot_topics": report["hot_topics"],
            "market_sentiment": report["market_sentiment"],
            "key_events": report["key_events"],
            "trend_analysis": report["trend_analysis"],
            "news_count": report["news_count"],
            "generated_at": report["generated_at"].isoformat() if report["generated_at"] else None,
        }


@router.get("/analysis/latest")
async def get_latest_report():
    """获取最新的每日分析报告"""
    async with async_session() as session:
        stmt = text("""
            SELECT date, overview, hot_topics, market_sentiment, key_events, 
                   trend_analysis, news_count, generated_at
            FROM daily_reports
            ORDER BY date DESC
            LIMIT 1
        """)
        result = await session.execute(stmt)
        report = result.mappings().first()
        
        if not report:
            return {"message": "暂无分析报告"}
        
        return {
            "date": str(report["date"]),
            "overview": report["overview"],
            "hot_topics": report["hot_topics"],
            "market_sentiment": report["market_sentiment"],
            "key_events": report["key_events"],
            "trend_analysis": report["trend_analysis"],
            "news_count": report["news_count"],
            "generated_at": report["generated_at"].isoformat() if report["generated_at"] else None,
        }


@router.get("/analysis/sentiment")
async def get_sentiment_stats(target_date: str = None):
    """获取情感分析统计"""
    if target_date:
        try:
            report_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式无效")
    else:
        report_date = date.today()
    
    async with async_session() as session:
        # 统计情感分布
        stmt = text("""
            SELECT 
                ai_sentiment,
                COUNT(*) as count,
                AVG(ai_sentiment_score) as avg_score,
                AVG(ai_importance) as avg_importance
            FROM news
            WHERE DATE(date) = :report_date
              AND ai_sentiment IS NOT NULL
            GROUP BY ai_sentiment
        """)
        result = await session.execute(stmt, {"report_date": report_date})
        sentiments = result.mappings().all()
        
        # 获取重要文章
        stmt_important = text("""
            SELECT id, title, translated_title, ai_sentiment, ai_sentiment_score, 
                   ai_summary_zh, ai_importance, category
            FROM news
            WHERE DATE(date) = :report_date
              AND ai_importance >= 0.7
            ORDER BY ai_importance DESC
            LIMIT 10
        """)
        result_important = await session.execute(stmt_important, {"report_date": report_date})
        important_articles = result_important.mappings().all()
        
        return {
            "date": str(report_date),
            "sentiment_distribution": [
                {
                    "sentiment": row["ai_sentiment"],
                    "count": row["count"],
                    "avg_score": round(float(row["avg_score"]), 2) if row["avg_score"] else 0,
                    "avg_importance": round(float(row["avg_importance"]), 2) if row["avg_importance"] else 0,
                }
                for row in sentiments
            ],
            "important_articles": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "translated_title": row["translated_title"],
                    "sentiment": row["ai_sentiment"],
                    "sentiment_score": round(float(row["ai_sentiment_score"]), 2) if row["ai_sentiment_score"] else 0,
                    "summary_zh": row["ai_summary_zh"],
                    "importance": round(float(row["ai_importance"]), 2) if row["ai_importance"] else 0,
                    "category": row["category"],
                }
                for row in important_articles
            ],
        }


@router.get("/analysis/trends")
async def get_trends(target_date: str = None, keyword: str = None, limit: int = 20):
    """获取趋势数据"""
    if target_date:
        try:
            report_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式无效")
    else:
        report_date = date.today()
    
    async with async_session() as session:
        stmt = text("""
            SELECT keyword, count, sentiment, trend, analysis, related_topics
            FROM trends
            WHERE date = :report_date
            ORDER BY count DESC
            LIMIT :limit
        """)
        result = await session.execute(stmt, {"report_date": report_date, "limit": limit})
        trends = result.mappings().all()
        
        return {
            "date": str(report_date),
            "trends": [
                {
                    "keyword": row["keyword"],
                    "count": row["count"],
                    "sentiment": row["sentiment"],
                    "trend": row["trend"],
                    "analysis": row["analysis"],
                    "related_topics": row["related_topics"],
                }
                for row in trends
            ],
        }


@router.get("/analysis/status")
async def get_analysis_status():
    """获取 AI 分析功能状态"""
    from scraper.pipeline.ai_analysis import is_ai_enabled
    
    async with async_session() as session:
        # 统计已分析和未分析的文章数量
        stmt_analyzed = text("""
            SELECT COUNT(*) FROM news WHERE ai_analyzed_at IS NOT NULL
        """)
        stmt_total = text("SELECT COUNT(*) FROM news")
        
        analyzed = (await session.execute(stmt_analyzed)).scalar()
        total = (await session.execute(stmt_total)).scalar()
        
        # 最近的报告日期
        stmt_latest = text("SELECT MAX(date) FROM daily_reports")
        latest_report = (await session.execute(stmt_latest)).scalar()
        
        return {
            "ai_enabled": is_ai_enabled(),
            "articles_analyzed": analyzed,
            "articles_total": total,
            "analysis_coverage": round(analyzed / total * 100, 1) if total > 0 else 0,
            "latest_report_date": str(latest_report) if latest_report else None,
        }
