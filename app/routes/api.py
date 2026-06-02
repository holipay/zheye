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
