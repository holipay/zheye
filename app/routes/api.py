from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import date, datetime
from sqlalchemy import select, func, desc, case, text, or_, cast, String
from models.base import async_session
from models.news import News
from models.keyword import Keyword
from models.article_keyword import ArticleKeyword
from models.article_relation import ArticleRelation
from models.entity import Entity
from models.article_entity import ArticleEntity
from models.daily_report import DailyReport
from models.trend import Trend
from app.cache import get_cached, set_cached

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
    cache_key = "api:categories:html"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    async with async_session() as session:
        query = select(News.category, func.count(News.id)).group_by(News.category).order_by(desc(func.count(News.id)))
        result = await session.execute(query)
        categories = result.all()
    
    response = templates.TemplateResponse(request=request, name="partials/categories.html", context={
        "categories": categories,
    })
    set_cached(cache_key, response.body.decode(), ttl=300)
    return response


@router.get("/article-types", response_class=HTMLResponse)
async def get_article_types(request: Request):
    cache_key = "api:article-types:html"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    async with async_session() as session:
        query = select(News.article_type, func.count(News.id)).group_by(News.article_type).order_by(desc(func.count(News.id)))
        result = await session.execute(query)
        article_types = result.all()
    
    response = templates.TemplateResponse(request=request, name="partials/article_types.html", context={
        "article_types": article_types,
    })
    set_cached(cache_key, response.body.decode(), ttl=300)
    return response


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
    cache_key = "api:meta"
    cached = get_cached(cache_key)
    if cached:
        return cached

    async with async_session() as session:
        count_result = await session.execute(select(func.count(News.id)))
        total = count_result.scalar()
        
        source_query = select(News.source, func.count(News.id)).group_by(News.source).order_by(desc(func.count(News.id)))
        source_result = await session.execute(source_query)
        sources = [{"name": row[0], "count": row[1]} for row in source_result.all()]
        
        category_query = select(News.category, func.count(News.id)).group_by(News.category).order_by(desc(func.count(News.id)))
        category_result = await session.execute(category_query)
        categories = [{"name": row[0], "count": row[1]} for row in category_result.all()]
    
    result = {
        "total": total,
        "sources": sources,
        "categories": categories,
    }
    set_cached(cache_key, result, ttl=300)
    return result


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
async def get_popular_keywords(request: Request, lang: str = "en", limit: int = 20):
    async with async_session() as session:
        query = (
            select(Keyword, func.count(ArticleKeyword.id).label("article_count"))
            .outerjoin(ArticleKeyword, ArticleKeyword.keyword_id == Keyword.id)
            .where(Keyword.lang == lang)
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
        "lang": lang,
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
    cache_key = "api:entity-types:html"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    async with async_session() as session:
        query = (
            select(Entity.entity_type, func.count(Entity.id))
            .group_by(Entity.entity_type)
            .order_by(desc(func.count(Entity.id)))
        )
        result = await session.execute(query)
        types = result.all()

    response = templates.TemplateResponse(request=request, name="partials/entity_types.html", context={
        "types": types,
    })
    set_cached(cache_key, response.body.decode(), ttl=300)
    return response


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
    cache_key = f"api:analysis:daily:{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        report_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")
    
    async with async_session() as session:
        result = await session.execute(
            select(DailyReport).where(DailyReport.date == report_date)
        )
        report = result.scalar_one_or_none()
        
        if not report:
            raise HTTPException(status_code=404, detail=f"未找到 {target_date} 的分析报告")
        
        data = {
            "date": str(report.date),
            "overview": report.overview,
            "hot_topics": report.hot_topics,
            "market_sentiment": report.market_sentiment,
            "key_events": report.key_events,
            "trend_analysis": report.trend_analysis,
            "news_count": report.news_count,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        }
        set_cached(cache_key, data, ttl=600)
        return data


@router.get("/analysis/latest")
async def get_latest_report():
    """获取最新的每日分析报告"""
    cache_key = "api:analysis:latest"
    cached = get_cached(cache_key)
    if cached:
        return cached

    async with async_session() as session:
        result = await session.execute(
            select(DailyReport).order_by(desc(DailyReport.date)).limit(1)
        )
        report = result.scalar_one_or_none()
        
        if not report:
            return {"message": "暂无分析报告"}
        
        data = {
            "date": str(report.date),
            "overview": report.overview,
            "hot_topics": report.hot_topics,
            "market_sentiment": report.market_sentiment,
            "key_events": report.key_events,
            "trend_analysis": report.trend_analysis,
            "news_count": report.news_count,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        }
        set_cached(cache_key, data, ttl=300)
        return data


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
    cache_key = f"api:analysis:trends:{target_date}:{keyword}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    if target_date:
        try:
            report_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式无效")
    else:
        report_date = date.today()
    
    async with async_session() as session:
        query = select(Trend).where(Trend.date == report_date)
        if keyword:
            query = query.where(Trend.keyword.ilike(f"%{keyword}%"))
        query = query.order_by(desc(Trend.count)).limit(limit)
        
        result = await session.execute(query)
        trends = result.scalars().all()
        
        data = {
            "date": str(report_date),
            "trends": [
                {
                    "keyword": t.keyword,
                    "count": t.count,
                    "sentiment": t.sentiment,
                    "trend": t.trend,
                    "analysis": t.analysis,
                    "related_topics": t.related_topics,
                }
                for t in trends
            ],
        }
        set_cached(cache_key, data, ttl=300)
        return data


@router.get("/analysis/status")
async def get_analysis_status():
    """获取 AI 分析功能状态"""
    from scraper.pipeline.ai_analysis import is_ai_enabled
    
    async with async_session() as session:
        stmt_analyzed = text("SELECT COUNT(*) FROM news WHERE ai_analyzed_at IS NOT NULL")
        stmt_total = text("SELECT COUNT(*) FROM news")
        
        analyzed = (await session.execute(stmt_analyzed)).scalar()
        total = (await session.execute(stmt_total)).scalar()
        
        stmt_latest = text("SELECT MAX(date) FROM daily_reports")
        latest_report = (await session.execute(stmt_latest)).scalar()
        
        return {
            "ai_enabled": is_ai_enabled(),
            "articles_analyzed": analyzed,
            "articles_total": total,
            "analysis_coverage": round(analyzed / total * 100, 1) if total > 0 else 0,
            "latest_report_date": str(latest_report) if latest_report else None,
        }


@router.get("/analysis/weekly/{target_date}")
async def get_weekly_report(target_date: str):
    """获取周报"""
    cache_key = f"api:analysis:weekly:{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        report_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")
    
    async with async_session() as session:
        # 计算周范围
        from datetime import timedelta
        weekday = report_date.weekday()
        start_date = report_date - timedelta(days=weekday)
        end_date = start_date + timedelta(days=6)
        
        result = await session.execute(text("""
            SELECT * FROM weekly_reports 
            WHERE period_start = :start_date
        """), {"start_date": start_date})
        report = result.mappings().first()
        
        if not report:
            raise HTTPException(status_code=404, detail=f"未找到 {start_date} 的周报")
        
        data = {
            "period": "weekly",
            "period_start": str(report["period_start"]),
            "period_end": str(report["period_end"]),
            "overview": report["overview"],
            "hot_topics": report["hot_topics"],
            "market_sentiment": report["market_sentiment"],
            "key_events": report["key_events"],
            "trend_analysis": report["trend_analysis"],
            "category_stats": report["category_stats"],
            "sentiment_stats": report["sentiment_stats"],
            "news_count": report["news_count"],
            "generated_at": report["generated_at"].isoformat() if report["generated_at"] else None,
        }
        set_cached(cache_key, data, ttl=600)
        return data


@router.get("/analysis/monthly/{target_date}")
async def get_monthly_report(target_date: str):
    """获取月报"""
    cache_key = f"api:analysis:monthly:{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        report_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")
    
    async with async_session() as session:
        # 计算月范围
        start_date = report_date.replace(day=1)
        
        result = await session.execute(text("""
            SELECT * FROM monthly_reports 
            WHERE period_start = :start_date
        """), {"start_date": start_date})
        report = result.mappings().first()
        
        if not report:
            raise HTTPException(status_code=404, detail=f"未找到 {start_date.strftime('%Y-%m')} 的月报")
        
        data = {
            "period": "monthly",
            "period_start": str(report["period_start"]),
            "period_end": str(report["period_end"]),
            "overview": report["overview"],
            "hot_topics": report["hot_topics"],
            "market_sentiment": report["market_sentiment"],
            "key_events": report["key_events"],
            "trend_analysis": report["trend_analysis"],
            "category_stats": report["category_stats"],
            "sentiment_stats": report["sentiment_stats"],
            "news_count": report["news_count"],
            "generated_at": report["generated_at"].isoformat() if report["generated_at"] else None,
        }
        set_cached(cache_key, data, ttl=600)
        return data


@router.get("/analysis/reports")
async def get_reports_list(period: str = "weekly", limit: int = 10):
    """获取报告列表"""
    cache_key = f"api:analysis:reports:{period}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # 使用白名单验证表名，防止 SQL 注入
    ALLOWED_TABLES = {"weekly_reports", "monthly_reports"}
    table_name = "weekly_reports" if period == "weekly" else "monthly_reports"
    
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail="无效的报告类型")
    
    async with async_session() as session:
        result = await session.execute(text(f"""
            SELECT period_start, period_end, overview, market_sentiment, news_count, generated_at
            FROM {table_name}
            ORDER BY period_start DESC
            LIMIT :limit
        """), {"limit": limit})
        
        reports = []
        for row in result.mappings():
            reports.append({
                "period_start": str(row["period_start"]),
                "period_end": str(row["period_end"]),
                "overview": row["overview"][:200] if row["overview"] else "",
                "market_sentiment": row["market_sentiment"],
                "news_count": row["news_count"],
                "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None,
            })
        
        data = {"period": period, "reports": reports}
        set_cached(cache_key, data, ttl=300)
        return data


@router.get("/search", response_class=HTMLResponse)
async def search_news(
    request: Request,
    q: str = "",
    category: str = "all",
    page: int = 1,
    page_size: int = 20,
):
    """全文搜索新闻"""
    if not q or len(q.strip()) < 2:
        return templates.TemplateResponse(request=request, name="partials/news_list.html", context={
            "news_items": [],
            "category": category,
            "page": 1,
            "total_pages": 0,
            "total": 0,
            "search_query": q,
        })

    offset = (page - 1) * page_size
    search_term = f"%{q.strip()}%"

    async with async_session() as session:
        base_filter = or_(
            News.title.ilike(search_term),
            News.translated_title.ilike(search_term),
            News.summary.ilike(search_term),
        )

        count_query = select(func.count(News.id)).where(base_filter)
        if category and category != "all":
            count_query = count_query.where(News.category == category)
        
        total_result = await session.execute(count_query)
        total = total_result.scalar()

        query = (
            select(News)
            .where(base_filter)
            .order_by(desc(News.date))
            .offset(offset)
            .limit(page_size)
        )
        if category and category != "all":
            query = query.where(News.category == category)

        result = await session.execute(query)
        news_items = result.scalars().all()

        total_pages = (total + page_size - 1) // page_size

    return templates.TemplateResponse(request=request, name="partials/news_list.html", context={
        "news_items": news_items,
        "category": category,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "search_query": q,
    })


# ============================================================
# 事件追踪 API
# ============================================================

@router.get("/events")
async def get_events(
    category: str = None,
    status: str = "active",
    page: int = 1,
    page_size: int = 20,
):
    """获取事件列表"""
    cache_key = f"api:events:{category}:{status}:{page}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    offset = (page - 1) * page_size

    async with async_session() as session:
        query = select(Event)
        count_query = select(func.count(Event.id))

        if category:
            query = query.where(Event.category == category)
            count_query = count_query.where(Event.category == category)
        if status:
            query = query.where(Event.status == status)
            count_query = count_query.where(Event.status == status)

        total_result = await session.execute(count_query)
        total = total_result.scalar()

        query = query.order_by(desc(Event.last_updated)).offset(offset).limit(page_size)
        result = await session.execute(query)
        events = result.scalars().all()

        event_list = []
        for event in events:
            event_list.append({
                "id": event.id,
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description,
                "category": event.category,
                "first_seen": str(event.first_seen) if event.first_seen else None,
                "last_updated": str(event.last_updated) if event.last_updated else None,
                "update_count": event.update_count,
                "status": event.status,
                "article_count": len(event.related_articles) if event.related_articles else 0,
            })

        total_pages = (total + page_size - 1) // page_size

        data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "events": event_list,
        }
        set_cached(cache_key, data, ttl=120)
        return data


@router.get("/events/{event_id}")
async def get_event_detail(event_id: str):
    """获取事件详情和时间线"""
    cache_key = f"api:events:detail:{event_id}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    async with async_session() as session:
        result = await session.execute(
            select(Event).where(Event.event_id == event_id)
        )
        event = result.scalar_one_or_none()

        if not event:
            raise HTTPException(status_code=404, detail="事件未找到")

        # 获取关联文章详情
        articles = []
        if event.related_articles:
            for article_ref in event.related_articles[:10]:
                if isinstance(article_ref, dict):
                    articles.append(article_ref)

        # 获取事件类型的其他事件（相关事件）
        related_events = []
        if event.data and event.data.get("event_type"):
            event_type = event.data["event_type"]
            related_result = await session.execute(
                select(Event)
                .where(Event.data["event_type"].as_string() == event_type)
                .where(Event.event_id != event_id)
                .order_by(desc(Event.last_updated))
                .limit(5)
            )
            for related in related_result.scalars().all():
                related_events.append({
                    "event_id": related.event_id,
                    "title": related.title,
                    "category": related.category,
                    "last_updated": str(related.last_updated) if related.last_updated else None,
                    "update_count": related.update_count,
                })

        data = {
            "event_id": event.event_id,
            "title": event.title,
            "description": event.description,
            "category": event.category,
            "first_seen": str(event.first_seen) if event.first_seen else None,
            "last_updated": str(event.last_updated) if event.last_updated else None,
            "update_count": event.update_count,
            "status": event.status,
            "event_type": event.data.get("event_type") if event.data else None,
            "timeline": articles,
            "related_events": related_events,
        }
        set_cached(cache_key, data, ttl=300)
        return data


@router.get("/events/timeline", response_class=HTMLResponse)
async def get_events_timeline(
    request: Request,
    category: str = None,
    days: int = 7,
    limit: int = 20,
):
    """获取事件时间线（HTML）"""
    from datetime import timedelta
    
    cache_key = f"api:events:timeline:{category}:{days}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    cutoff_date = date.today() - timedelta(days=days)

    async with async_session() as session:
        query = select(Event).where(Event.last_updated >= cutoff_date)
        if category:
            query = query.where(Event.category == category)
        query = query.order_by(desc(Event.last_updated)).limit(limit)

        result = await session.execute(query)
        events = result.scalars().all()

        event_list = []
        for event in events:
            event_list.append({
                "event_id": event.event_id,
                "title": event.title,
                "category": event.category,
                "first_seen": str(event.first_seen) if event.first_seen else None,
                "last_updated": str(event.last_updated) if event.last_updated else None,
                "update_count": event.update_count,
                "status": event.status,
                "article_count": len(event.related_articles) if event.related_articles else 0,
            })

    response = templates.TemplateResponse(request=request, name="partials/events_timeline.html", context={
        "events": event_list,
        "category": category,
        "days": days,
    })
    set_cached(cache_key, response.body.decode(), ttl=120)
    return response


@router.get("/events/categories")
async def get_event_categories():
    """获取事件分类统计"""
    cache_key = "api:events:categories"
    cached = get_cached(cache_key)
    if cached:
        return cached

    async with async_session() as session:
        query = (
            select(Event.category, func.count(Event.id))
            .where(Event.status == "active")
            .group_by(Event.category)
            .order_by(desc(func.count(Event.id)))
        )
        result = await session.execute(query)
        categories = [{"name": row[0], "count": row[1]} for row in result.all()]

        data = {"categories": categories}
        set_cached(cache_key, data, ttl=300)
        return data


# ============================================================
# 知识模型 API (P0)
# ============================================================

@router.get("/events/{event_id}/knowledge", response_class=HTMLResponse)
async def get_event_knowledge(request: Request, event_id: str, lang: str = "zh"):
    """获取事件的知识框架（背景、缺口、因果链）"""
    cache_key = f"api:events:knowledge:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    async with async_session() as session:
        # 获取事件知识框架
        from models.knowledge import EventKnowledge, EventKnowledgeAtom, KnowledgeAtom
        
        result = await session.execute(
            select(EventKnowledge).where(EventKnowledge.event_id == event_id)
        )
        knowledge = result.scalar_one_or_none()
        
        if not knowledge:
            return templates.TemplateResponse(request=request, name="partials/knowledge_empty.html", context={
                "event_id": event_id,
                "lang": lang,
            })
        
        # 获取关联的知识原子
        atoms_query = (
            select(KnowledgeAtom, EventKnowledgeAtom.relevance, EventKnowledgeAtom.position, EventKnowledgeAtom.is_required)
            .join(EventKnowledgeAtom, EventKnowledgeAtom.atom_id == KnowledgeAtom.id)
            .where(EventKnowledgeAtom.event_id == event_id)
            .where(KnowledgeAtom.lang == lang)
            .order_by(EventKnowledgeAtom.position)
        )
        atoms_result = await session.execute(atoms_query)
        atoms = []
        for atom, relevance, position, is_required in atoms_result.all():
            atoms.append({
                "id": atom.id,
                "type": atom.atom_type,
                "title": atom.title,
                "content": atom.content,
                "entities": atom.entities or [],
                "keywords": atom.keywords or [],
                "relevance": relevance,
                "is_required": is_required,
            })

    response = templates.TemplateResponse(request=request, name="partials/event_knowledge.html", context={
        "event_id": event_id,
        "lang": lang,
        "background_summary": knowledge.background_summary,
        "knowledge_gaps": knowledge.knowledge_gaps or [],
        "causal_chain": knowledge.causal_chain or [],
        "key_concepts": knowledge.key_concepts or [],
        "atoms": atoms,
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/knowledge/analyze")
async def trigger_knowledge_analysis(event_id: str):
    """触发事件知识分析（手动或自动）"""
    from scraper.pipeline.ai_analysis import DeepSeekClient
    from scraper.pipeline.knowledge import analyze_event_knowledge
    from models.knowledge import EventKnowledge, EventKnowledgeAtom, KnowledgeAtom
    
    async with async_session() as session:
        # 获取事件
        result = await session.execute(
            select(Event).where(Event.event_id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            raise HTTPException(status_code=404, detail="事件未找到")
        
        # 获取相关文章
        articles = []
        if event.related_articles:
            for article_ref in event.related_articles[:5]:
                if isinstance(article_ref, dict):
                    articles.append(article_ref)
        
        # 调用AI分析
        ai_client = DeepSeekClient()
        event_data = {
            "title": event.title,
            "description": event.description,
            "category": event.category,
        }
        
        analysis = await analyze_event_knowledge(event_data, articles, ai_client)
        
        if not analysis:
            raise HTTPException(status_code=500, detail="知识分析失败")
        
        # 保存知识框架
        existing = await session.execute(
            select(EventKnowledge).where(EventKnowledge.event_id == event_id)
        )
        ek = existing.scalar_one_or_none()
        
        if ek:
            # 更新
            ek.background_summary = analysis.get('background_summary')
            ek.knowledge_gaps = analysis.get('knowledge_gaps')
            ek.causal_chain = analysis.get('causal_chain')
            ek.key_concepts = analysis.get('key_concepts')
            ek.ai_model = analysis.get('ai_model')
            ek.ai_confidence = analysis.get('ai_confidence')
            ek.analysis_version += 1
        else:
            # 新建
            ek = EventKnowledge(
                event_id=event_id,
                background_summary=analysis.get('background_summary'),
                knowledge_gaps=analysis.get('knowledge_gaps'),
                causal_chain=analysis.get('causal_chain'),
                key_concepts=analysis.get('key_concepts'),
                ai_model=analysis.get('ai_model'),
                ai_confidence=analysis.get('ai_confidence'),
            )
            session.add(ek)
        
        # 保存知识原子
        for atom_data in analysis.get('knowledge_atoms', []):
            # 查找或创建知识原子
            existing_atom = await session.execute(
                select(KnowledgeAtom).where(
                    KnowledgeAtom.title == atom_data['title'],
                    KnowledgeAtom.lang == 'zh'
                )
            )
            atom = existing_atom.scalar_one_or_none()
            
            if not atom:
                atom = KnowledgeAtom(
                    atom_type=atom_data['atom_type'],
                    title=atom_data['title'],
                    content=atom_data['content'],
                    category=event.category,
                    entities=atom_data.get('entities'),
                    keywords=atom_data.get('keywords'),
                    lang='zh',
                )
                session.add(atom)
                await session.flush()  # 获取ID
            
            # 关联
            existing_link = await session.execute(
                select(EventKnowledgeAtom).where(
                    EventKnowledgeAtom.event_id == event_id,
                    EventKnowledgeAtom.atom_id == atom.id
                )
            )
            if not existing_link.scalar():
                link = EventKnowledgeAtom(
                    event_id=event_id,
                    atom_id=atom.id,
                    relevance=1.0,
                    position=len(analysis.get('knowledge_atoms', [])),
                )
                session.add(link)
        
        await session.commit()
        
        # 清除缓存
        from app.cache import invalidate_cache
        invalidate_cache(f"api:events:knowledge:{event_id}")
        
        return {"status": "ok", "event_id": event_id, "version": ek.analysis_version}


# P1: 因果链 API

@router.get("/events/{event_id}/causal-chain", response_class=HTMLResponse)
async def get_event_causal_chain(request: Request, event_id: str, lang: str = "zh"):
    """获取事件的因果链结构"""
    cache_key = f"api:events:causal:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    async with async_session() as session:
        from models.causal_chain import CausalNode, CausalLink
        
        # 获取因果节点
        nodes_result = await session.execute(
            select(CausalNode)
            .where(CausalNode.event_id == event_id)
            .order_by(CausalNode.node_type, CausalNode.id)
        )
        nodes = nodes_result.scalars().all()
        
        if not nodes:
            return templates.TemplateResponse(request=request, name="partials/causal_chain_empty.html", context={
                "event_id": event_id,
                "lang": lang,
            })
        
        # 获取因果关系
        node_ids = [n.id for n in nodes]
        links_result = await session.execute(
            select(CausalLink)
            .where(CausalLink.source_node_id.in_(node_ids))
        )
        links = links_result.scalars().all()
        
        # 构建节点数据
        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "id": node.id,
                "type": node.node_type,
                "title": node.title,
                "description": node.description,
                "probability": node.probability,
                "impact_level": node.impact_level,
                "time_horizon": node.time_horizon,
                "entities": node.entities or [],
                "confidence": node.confidence,
            })
        
        # 构建关系数据
        links_data = []
        for link in links:
            links_data.append({
                "source": link.source_node_id,
                "target": link.target_node_id,
                "type": link.link_type,
                "strength": link.strength,
                "description": link.description,
            })

    response = templates.TemplateResponse(request=request, name="partials/causal_chain.html", context={
        "event_id": event_id,
        "lang": lang,
        "nodes": nodes_data,
        "links": links_data,
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/causal-chain/analyze")
async def trigger_causal_chain_analysis(event_id: str):
    """触发因果链分析"""
    from scraper.pipeline.ai_analysis import DeepSeekClient
    from scraper.pipeline.knowledge import analyze_causal_chain
    from models.causal_chain import CausalNode, CausalLink
    
    async with async_session() as session:
        # 获取事件
        result = await session.execute(
            select(Event).where(Event.event_id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            raise HTTPException(status_code=404, detail="事件未找到")
        
        # 获取相关文章
        articles = []
        if event.related_articles:
            for article_ref in event.related_articles[:5]:
                if isinstance(article_ref, dict):
                    articles.append(article_ref)
        
        # 调用AI分析
        ai_client = DeepSeekClient()
        event_data = {
            "title": event.title,
            "description": event.description,
            "category": event.category,
        }
        
        analysis = await analyze_causal_chain(event_data, articles, ai_client)
        
        if not analysis:
            raise HTTPException(status_code=500, detail="因果链分析失败")
        
        # 删除旧的因果节点
        old_nodes = await session.execute(
            select(CausalNode).where(CausalNode.event_id == event_id)
        )
        for node in old_nodes.scalars().all():
            await session.delete(node)
        
        # 保存新的因果节点
        node_id_map = {}  # AI返回的ID -> 数据库ID
        for node_data in analysis.get('nodes', []):
            node = CausalNode(
                event_id=event_id,
                node_type=node_data['node_type'],
                title=node_data['title'],
                description=node_data.get('description'),
                probability=node_data.get('probability'),
                impact_level=node_data.get('impact_level'),
                time_horizon=node_data.get('time_horizon'),
                entities=node_data.get('entities'),
                confidence=node_data.get('confidence', 0.8),
            )
            session.add(node)
            await session.flush()
            node_id_map[node_data['id']] = node.id
        
        # 保存因果关系
        for link_data in analysis.get('links', []):
            source_id = node_id_map.get(link_data['source'])
            target_id = node_id_map.get(link_data['target'])
            
            if source_id and target_id:
                link = CausalLink(
                    source_node_id=source_id,
                    target_node_id=target_id,
                    link_type=link_data.get('link_type', 'causes'),
                    strength=link_data.get('strength', 1.0),
                    description=link_data.get('description'),
                )
                session.add(link)
        
        await session.commit()
        
        # 清除缓存
        from app.cache import invalidate_cache
        invalidate_cache(f"api:events:causal:{event_id}")
        
        return {
            "status": "ok",
            "event_id": event_id,
            "nodes_count": len(analysis.get('nodes', [])),
            "links_count": len(analysis.get('links', [])),
            "summary": analysis.get('summary'),
        }


# ============================================================
# P1: 历史类比检索 API
# ============================================================

@router.get("/events/{event_id}/analogies", response_class=HTMLResponse)
async def get_event_analogies(request: Request, event_id: str, lang: str = "zh"):
    """获取事件的历史类比"""
    cache_key = f"api:events:analogies:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    async with async_session() as session:
        from models.event_representation import HistoricalAnalogy, EventRepresentation
        
        # 获取事件表征
        repr_result = await session.execute(
            select(EventRepresentation).where(EventRepresentation.event_id == event_id)
        )
        source_repr = repr_result.scalar_one_or_none()
        
        # 获取历史类比
        analogies_result = await session.execute(
            select(HistoricalAnalogy, Event)
            .join(Event, Event.event_id == HistoricalAnalogy.target_event_id)
            .where(HistoricalAnalogy.source_event_id == event_id)
            .order_by(HistoricalAnalogy.overall_similarity.desc())
            .limit(5)
        )
        analogies = []
        for analogy, target_event in analogies_result.all():
            analogies.append({
                "id": analogy.id,
                "target_event_id": analogy.target_event_id,
                "target_title": target_event.title,
                "target_category": target_event.category,
                "overall_similarity": analogy.overall_similarity,
                "causal_similarity": analogy.causal_similarity,
                "decision_similarity": analogy.decision_similarity,
                "constraint_similarity": analogy.constraint_similarity,
                "mechanism_similarity": analogy.mechanism_similarity,
                "game_similarity": analogy.game_similarity,
                "analogy_type": analogy.analogy_type,
                "analogy_summary": analogy.analogy_summary,
                "key_insight": analogy.key_insight,
                "lessons_learned": analogy.lessons_learned,
                "surface_differences": analogy.surface_differences or [],
                "structural_differences": analogy.structural_differences or [],
            })

    if not analogies and not source_repr:
        return templates.TemplateResponse(request=request, name="partials/analogy_empty.html", context={
            "event_id": event_id,
            "lang": lang,
        })

    response = templates.TemplateResponse(request=request, name="partials/event_analogies.html", context={
        "event_id": event_id,
        "lang": lang,
        "source_repr": {
            "causal_pattern": source_repr.causal_pattern_desc if source_repr else None,
            "economic_principle": source_repr.economic_principle_desc if source_repr else None,
        } if source_repr else None,
        "analogies": analogies,
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/analogies/analyze")
async def trigger_analogy_analysis(event_id: str):
    """触发历史类比分析"""
    from scraper.pipeline.ai_analysis import DeepSeekClient
    from scraper.pipeline.analogy import extract_event_representation, analyze_analogy, compute_structural_similarity
    from models.event_representation import EventRepresentation, HistoricalAnalogy
    
    async with async_session() as session:
        # 获取事件
        result = await session.execute(
            select(Event).where(Event.event_id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            raise HTTPException(status_code=404, detail="事件未找到")
        
        # 获取相关文章
        articles = []
        if event.related_articles:
            for article_ref in event.related_articles[:5]:
                if isinstance(article_ref, dict):
                    articles.append(article_ref)
        
        ai_client = DeepSeekClient()
        event_data = {
            "title": event.title,
            "description": event.description,
            "category": event.category,
        }
        
        # 步骤1: 提取当前事件的表征
        repr_result = await extract_event_representation(event_data, articles, ai_client)
        if not repr_result:
            raise HTTPException(status_code=500, detail="表征提取失败")
        
        # 保存表征
        existing_repr = await session.execute(
            select(EventRepresentation).where(EventRepresentation.event_id == event_id)
        )
        er = existing_repr.scalar_one_or_none()
        
        surface = repr_result.get('surface', {})
        structural = repr_result.get('structural', {})
        abstract = repr_result.get('abstract', {})
        
        if er:
            er.surface_summary = surface.get('summary')
            er.surface_entities = surface.get('entities')
            er.surface_numbers = surface.get('numbers')
            er.causal_pattern = structural.get('causal_pattern')
            er.causal_pattern_desc = structural.get('causal_pattern_desc')
            er.decision_logic = structural.get('decision_logic')
            er.transmission_mechanism = structural.get('transmission_mechanism')
            er.constraint_conditions = structural.get('constraint_conditions')
            er.economic_principle = abstract.get('economic_principle')
            er.economic_principle_desc = abstract.get('economic_principle_desc')
            er.game_theory_structure = abstract.get('game_theory_structure')
            er.institutional_context = abstract.get('institutional_context')
            er.ai_model = repr_result.get('ai_model')
            er.ai_confidence = repr_result.get('ai_confidence')
        else:
            er = EventRepresentation(
                event_id=event_id,
                surface_summary=surface.get('summary'),
                surface_entities=surface.get('entities'),
                surface_numbers=surface.get('numbers'),
                causal_pattern=structural.get('causal_pattern'),
                causal_pattern_desc=structural.get('causal_pattern_desc'),
                decision_logic=structural.get('decision_logic'),
                transmission_mechanism=structural.get('transmission_mechanism'),
                constraint_conditions=structural.get('constraint_conditions'),
                economic_principle=abstract.get('economic_principle'),
                economic_principle_desc=abstract.get('economic_principle_desc'),
                game_theory_structure=abstract.get('game_theory_structure'),
                institutional_context=abstract.get('institutional_context'),
                ai_model=repr_result.get('ai_model'),
                ai_confidence=repr_result.get('ai_confidence'),
            )
            session.add(er)
        
        await session.flush()
        
        # 步骤2: 查找候选历史事件（基于规则的预筛选）
        # 优先匹配相同因果模式或经济学原理的事件
        candidates_query = (
            select(EventRepresentation)
            .where(EventRepresentation.event_id != event_id)
            .where(
                (EventRepresentation.causal_pattern == structural.get('causal_pattern')) |
                (EventRepresentation.economic_principle == abstract.get('economic_principle'))
            )
            .limit(10)
        )
        candidates_result = await session.execute(candidates_query)
        candidates = candidates_result.scalars().all()
        
        # 步骤3: 对每个候选进行详细的类比分析
        analogies_created = 0
        for candidate in candidates:
            # 检查是否已存在
            existing = await session.execute(
                select(HistoricalAnalogy).where(
                    HistoricalAnalogy.source_event_id == event_id,
                    HistoricalAnalogy.target_event_id == candidate.event_id
                )
            )
            if existing.scalar():
                continue
            
            # 计算规则相似度
            rule_scores = compute_structural_similarity(
                repr_result,
                {
                    'structural': {
                        'causal_pattern': candidate.causal_pattern,
                        'constraint_conditions': candidate.constraint_conditions or [],
                    },
                    'abstract': {
                        'economic_principle': candidate.economic_principle,
                    }
                }
            )
            
            # 如果规则相似度太低，跳过AI分析
            if rule_scores['overall'] < 0.3:
                continue
            
            # 调用AI进行详细类比分析
            source_data = {
                'title': event.title,
                'causal_pattern_desc': structural.get('causal_pattern_desc'),
                'decision_logic': structural.get('decision_logic'),
                'transmission_mechanism': structural.get('transmission_mechanism'),
                'economic_principle_desc': abstract.get('economic_principle_desc'),
            }
            target_data = {
                'title': candidate.surface_summary,
                'causal_pattern_desc': candidate.causal_pattern_desc,
                'decision_logic': candidate.decision_logic,
                'transmission_mechanism': candidate.transmission_mechanism,
                'economic_principle_desc': candidate.economic_principle_desc,
            }
            
            analogy_result = await analyze_analogy(source_data, target_data, ai_client)
            if not analogy_result:
                continue
            
            # 保存类比
            analogy = HistoricalAnalogy(
                source_event_id=event_id,
                target_event_id=candidate.event_id,
                causal_similarity=analogy_result.get('causal_similarity'),
                decision_similarity=analogy_result.get('decision_similarity'),
                constraint_similarity=analogy_result.get('constraint_similarity'),
                mechanism_similarity=analogy_result.get('mechanism_similarity'),
                game_similarity=analogy_result.get('game_similarity'),
                overall_similarity=analogy_result.get('overall_similarity'),
                analogy_type=analogy_result.get('analogy_type'),
                analogy_summary=analogy_result.get('analogy_summary'),
                key_insight=analogy_result.get('key_insight'),
                lessons_learned=analogy_result.get('lessons_learned'),
                surface_differences=analogy_result.get('surface_differences'),
                structural_differences=analogy_result.get('structural_differences'),
                confidence=analogy_result.get('confidence'),
                ai_model=analogy_result.get('ai_model'),
            )
            session.add(analogy)
            analogies_created += 1
        
        await session.commit()
        
        # 清除缓存
        from app.cache import invalidate_cache
        invalidate_cache(f"api:events:analogies:{event_id}")
        
        return {
            "status": "ok",
            "event_id": event_id,
            "representation_extracted": True,
            "candidates_found": len(candidates),
            "analogies_created": analogies_created,
        }


# ============================================================
# P2: 未来情景推演 API
# ============================================================

@router.get("/events/{event_id}/scenarios", response_class=HTMLResponse)
async def get_event_scenarios(request: Request, event_id: str, lang: str = "zh"):
    """获取事件的情景推演框架"""
    cache_key = f"api:events:scenarios:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    async with async_session() as session:
        from models.scenario import EventScenario
        
        result = await session.execute(
            select(EventScenario).where(EventScenario.event_id == event_id)
        )
        scenario = result.scalar_one_or_none()
        
        if not scenario:
            return templates.TemplateResponse(request=request, name="partials/scenario_empty.html", context={
                "event_id": event_id,
                "lang": lang,
            })

    response = templates.TemplateResponse(request=request, name="partials/event_scenarios.html", context={
        "event_id": event_id,
        "lang": lang,
        "key_variables": scenario.key_variables or [],
        "observation_signals": scenario.observation_signals or [],
        "scenarios": scenario.scenarios or [],
        "thinking_questions": scenario.thinking_questions or [],
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/scenarios/analyze")
async def trigger_scenario_analysis(event_id: str):
    """触发情景推演分析"""
    from scraper.pipeline.ai_analysis import DeepSeekClient
    from scraper.pipeline.scenario import analyze_scenarios
    from models.scenario import EventScenario
    from models.event_representation import EventRepresentation
    
    async with async_session() as session:
        # 获取事件
        result = await session.execute(
            select(Event).where(Event.event_id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            raise HTTPException(status_code=404, detail="事件未找到")
        
        # 获取相关文章
        articles = []
        if event.related_articles:
            for article_ref in event.related_articles[:5]:
                if isinstance(article_ref, dict):
                    articles.append(article_ref)
        
        # 获取因果模式（如果已有表征）
        repr_result = await session.execute(
            select(EventRepresentation).where(EventRepresentation.event_id == event_id)
        )
        representation = repr_result.scalar_one_or_none()
        causal_pattern = representation.causal_pattern_desc if representation else None
        
        # 调用AI分析
        ai_client = DeepSeekClient()
        event_data = {
            "title": event.title,
            "description": event.description,
            "category": event.category,
        }
        
        analysis = await analyze_scenarios(event_data, articles, ai_client, causal_pattern)
        
        if not analysis:
            raise HTTPException(status_code=500, detail="情景分析失败")
        
        # 保存情景推演
        existing = await session.execute(
            select(EventScenario).where(EventScenario.event_id == event_id)
        )
        es = existing.scalar_one_or_none()
        
        if es:
            es.key_variables = analysis.get('key_variables')
            es.observation_signals = analysis.get('observation_signals')
            es.scenarios = analysis.get('scenarios')
            es.thinking_questions = analysis.get('thinking_questions')
            es.ai_model = analysis.get('ai_model')
            es.ai_confidence = analysis.get('ai_confidence')
        else:
            es = EventScenario(
                event_id=event_id,
                key_variables=analysis.get('key_variables'),
                observation_signals=analysis.get('observation_signals'),
                scenarios=analysis.get('scenarios'),
                thinking_questions=analysis.get('thinking_questions'),
                ai_model=analysis.get('ai_model'),
                ai_confidence=analysis.get('ai_confidence'),
            )
            session.add(es)
        
        await session.commit()
        
        # 清除缓存
        from app.cache import invalidate_cache
        invalidate_cache(f"api:events:scenarios:{event_id}")
        
        return {
            "status": "ok",
            "event_id": event_id,
            "key_variables_count": len(analysis.get('key_variables', [])),
            "scenarios_count": len(analysis.get('scenarios', [])),
        }
