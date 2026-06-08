from fastapi import Request, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from datetime import date, datetime
from sqlalchemy import select, func, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import get_session
from models.news import News
from models.keyword import Keyword
from models.article_keyword import ArticleKeyword
from models.article_relation import ArticleRelation
from models.entity import Entity
from models.article_entity import ArticleEntity
from app.cache import get_cached, set_cached
from app.config import settings
from app.routes.api_common import router, templates, _get_api_context, limiter


@router.get("/news", response_class=HTMLResponse)
@limiter.limit(settings.RATE_LIMIT_API)
async def get_news(
    request: Request,
    session: AsyncSession = Depends(get_session),
    category: str = "all",
    article_type: str = "all",
    keyword_id: int = None,
    sort: str = "date",
    page: int = Query(default=1, ge=1, description="页码"),
):
    page_size = settings.DEFAULT_PAGE_SIZE
    offset = (page - 1) * page_size

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

    ctx = _get_api_context(request, news_items=news_items, category=category, article_type=article_type,
                           keyword_id=keyword_id, sort=sort, page=page, total_pages=total_pages, total=total)
    return templates.TemplateResponse(request=request, name="partials/news_list.html", context=ctx)


@router.get("/categories", response_class=HTMLResponse)
async def get_categories(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    lang = request.query_params.get("lang", "en")
    cache_key = f"api:categories:html:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    query = select(News.category, func.count(News.id)).group_by(News.category).order_by(desc(func.count(News.id)))
    result = await session.execute(query)
    categories = result.all()
    
    response = templates.TemplateResponse(request=request, name="partials/categories.html", context=_get_api_context(
        request, categories=categories,
    ))
    set_cached(cache_key, response.body.decode(), ttl=300)
    return response


@router.get("/article-types", response_class=HTMLResponse)
async def get_article_types(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    lang = request.query_params.get("lang", "en")
    cache_key = f"api:article-types:html:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    query = select(News.article_type, func.count(News.id)).group_by(News.article_type).order_by(desc(func.count(News.id)))
    result = await session.execute(query)
    article_types = result.all()
    
    response = templates.TemplateResponse(request=request, name="partials/article_types.html", context=_get_api_context(
        request, article_types=article_types,
    ))
    set_cached(cache_key, response.body.decode(), ttl=300)
    return response


@router.get("/latest", response_class=HTMLResponse)
async def get_latest(
    request: Request,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=10, le=100),
):
    query = select(News).order_by(desc(News.created_at)).limit(limit)
    result = await session.execute(query)
    news_items = result.scalars().all()
    
    return templates.TemplateResponse(request=request, name="partials/news_list.html", context=_get_api_context(
        request, news_items=news_items, category="all", article_type="all", sort="date",
        page=1, total_pages=1, total=len(news_items),
    ))


@router.get("/articles", response_class=HTMLResponse)
async def get_articles(
    request: Request,
    session: AsyncSession = Depends(get_session),
    sort: str = "date",
    page: int = 1,
):
    page_size = settings.DEFAULT_PAGE_SIZE
    offset = (page - 1) * page_size

    # 只获取有完整内容的文章
    base_query = select(News).where(News.content.isnot(None), News.content != "")
    count_query = select(func.count(News.id)).where(News.content.isnot(None), News.content != "")

    total_result = await session.execute(count_query)
    total = total_result.scalar()
    total_pages = max(1, (total + page_size - 1) // page_size)

    if sort == "weight":
        query = base_query.order_by(desc(News.ai_importance), desc(News.date))
    else:
        query = base_query.order_by(desc(News.date))

    query = query.offset(offset).limit(page_size)
    result = await session.execute(query)
    news_items = result.scalars().all()

    return templates.TemplateResponse(request=request, name="partials/articles_list.html", context=_get_api_context(
        request, news_items=news_items, sort=sort,
        page=page, total_pages=total_pages, total=total,
    ))


@router.get("/meta")
async def get_meta(session: AsyncSession = Depends(get_session)):
    cache_key = "api:meta"
    cached = get_cached(cache_key)
    if cached:
        return cached

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
async def get_related_news(
    news_id: int,
    session: AsyncSession = Depends(get_session),
    limit: int = 10,
):
    news_result = await session.execute(select(News).where(News.id == news_id))
    news = news_result.scalar_one_or_none()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    # 使用 OR 条件查询两个方向的关系
    query = (
        select(News, ArticleRelation.score)
        .join(
            ArticleRelation,
            or_(
                and_(ArticleRelation.source_id == news_id, ArticleRelation.target_id == News.id),
                and_(ArticleRelation.target_id == news_id, ArticleRelation.source_id == News.id),
            )
        )
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
async def get_keywords(
    session: AsyncSession = Depends(get_session),
    category: str = None,
    lang: str = None,
    page: int = 1,
    page_size: int = 50,
):
    # 使用子查询一次性获取文章计数，避免 N+1 查询
    article_count_subq = (
        select(
            ArticleKeyword.keyword_id,
            func.count(ArticleKeyword.id).label("article_count")
        )
        .group_by(ArticleKeyword.keyword_id)
        .subquery()
    )

    query = (
        select(Keyword, func.coalesce(article_count_subq.c.article_count, 0).label("article_count"))
        .outerjoin(article_count_subq, Keyword.id == article_count_subq.c.keyword_id)
    )
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
    rows = result.all()

    keyword_list = []
    for kw, article_count in rows:
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
async def get_popular_keywords(
    request: Request,
    session: AsyncSession = Depends(get_session),
    lang: str = "en",
    limit: int = 20,
):
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

    return templates.TemplateResponse(request=request, name="partials/keywords.html", context=_get_api_context(
        request, keywords=keywords,
    ))


@router.get("/keywords/{keyword_id}/articles")
async def get_articles_by_keyword(
    keyword_id: int,
    session: AsyncSession = Depends(get_session),
    page: int = 1,
    page_size: int = 20,
):
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
async def get_news_detail(
    request: Request,
    news_id: int,
    session: AsyncSession = Depends(get_session),
):
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
        .join(
            ArticleRelation,
            or_(
                and_(ArticleRelation.source_id == news_id, ArticleRelation.target_id == News.id),
                and_(ArticleRelation.target_id == news_id, ArticleRelation.source_id == News.id),
            )
        )
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

    return templates.TemplateResponse(request=request, name="partials/news_detail.html", context=_get_api_context(
        request, news=news, keywords=keywords, entities=entities, related=related,
    ))


@router.get("/entities/popular", response_class=HTMLResponse)
async def get_popular_entities(
    request: Request,
    session: AsyncSession = Depends(get_session),
    entity_type: str = None,
    limit: int = 15,
):
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

    return templates.TemplateResponse(request=request, name="partials/entity_list.html", context=_get_api_context(
        request, entities=entities, entity_type=entity_type,
    ))


@router.get("/entities/types", response_class=HTMLResponse)
async def get_entity_types(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    lang = request.query_params.get("lang", "en")
    cache_key = f"api:entity-types:html:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

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
async def get_news_by_entity(
    request: Request,
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    page: int = 1,
    page_size: int = 20,
):
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

    return templates.TemplateResponse(request=request, name="partials/news_list.html", context=_get_api_context(
        request, news_items=news_items, category="all", article_type="all", sort="date",
        page=page, total_pages=total_pages, total=total,
    ))


@router.get("/search", response_class=HTMLResponse)
@limiter.limit(settings.RATE_LIMIT_API)
async def search_news(
    request: Request,
    session: AsyncSession = Depends(get_session),
    q: str = "",
    category: str = "all",
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
):
    """全文搜索新闻 - 使用 PostgreSQL 全文搜索"""
    if not q or len(q.strip()) < 2:
        return templates.TemplateResponse(request=request, name="partials/news_list.html", context=_get_api_context(
            request, news_items=[], category=category, article_type="all", sort="date",
            page=1, total_pages=0, total=0, search_query=q,
        ))

    offset = (page - 1) * page_size
    search_term = q.strip()
    
    # 使用 PostgreSQL 全文搜索
    # to_tsvector('simple', ...) 配合 plainto_tsquery('simple', ...) 支持中英文
    ts_query = func.plainto_tsquery('simple', search_term)
    ts_vector = func.to_tsvector('simple', 
        News.title + ' ' + func.coalesce(News.translated_title, '') + ' ' + func.coalesce(News.content, '')
    )
    
    # 使用 @@ 运算符进行全文搜索匹配
    base_filter = ts_vector.op('@@')(ts_query)

    count_query = select(func.count(News.id)).where(base_filter)
    if category and category != "all":
        count_query = count_query.where(News.category == category)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # 使用 ts_rank 进行相关性排序
    rank = func.ts_rank(ts_vector, ts_query).label("rank")
    
    query = (
        select(News, rank)
        .where(base_filter)
        .order_by(desc(rank), desc(News.date))
        .offset(offset)
        .limit(page_size)
    )
    if category and category != "all":
        query = query.where(News.category == category)

    result = await session.execute(query)
    rows = result.all()
    news_items = [row[0] for row in rows]

    total_pages = (total + page_size - 1) // page_size

    return templates.TemplateResponse(request=request, name="partials/news_list.html", context=_get_api_context(
        request, news_items=news_items, category=category, article_type="all", sort="date",
        page=page, total_pages=total_pages, total=total, search_query=q,
    ))
