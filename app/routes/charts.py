"""
图表数据 API
提供各类图表所需的数据
"""

import logging
from datetime import date, timedelta
from fastapi import APIRouter, Query, Request
from sqlalchemy import select, func, desc, text

from models.base import async_session
from models.news import News
from models.trend import Trend
from app.cache import get_cached, set_cached
from app.i18n import get_text, get_language_from_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/charts")


@router.get("/daily-trend")
async def get_daily_trend(days: int = Query(default=30, le=90)):
    """获取每日新闻趋势数据"""
    cache_key = f"charts:daily-trend:{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    start_date = date.today() - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT DATE(date) as day, COUNT(*) as count
            FROM news
            WHERE date >= :start_date
            GROUP BY DATE(date)
            ORDER BY day
        """), {"start_date": start_date})

        data = []
        for row in result:
            data.append({
                "date": str(row[0]),
                "count": row[1]
            })

        # 填充缺失日期
        if data:
            all_dates = []
            current = start_date
            end = date.today()
            while current <= end:
                all_dates.append(str(current))
                current += timedelta(days=1)

            date_map = {d["date"]: d["count"] for d in data}
            filled_data = [
                {"date": d, "count": date_map.get(d, 0)}
                for d in all_dates
            ]
        else:
            filled_data = data

        response = {
            "labels": [d["date"] for d in filled_data],
            "values": [d["count"] for d in filled_data],
            "total": sum(d["count"] for d in filled_data)
        }
        set_cached(cache_key, response, ttl=600)
        return response


@router.get("/sentiment")
async def get_sentiment_distribution(request: Request, days: int = Query(default=7, le=30)):
    """获取情感分布数据"""
    lang = get_language_from_request(request)
    cache_key = f"charts:sentiment:{days}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    start_date = date.today() - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT 
                COALESCE(ai_sentiment, 'unknown') as sentiment,
                COUNT(*) as count
            FROM news
            WHERE date >= :start_date
            GROUP BY ai_sentiment
        """), {"start_date": start_date})

        sentiment_map = {"positive": 0, "neutral": 0, "negative": 0, "unknown": 0}
        for row in result:
            sentiment_map[row[0]] = row[1]

        # 根据语言返回标签
        if lang == "zh":
            labels = ["积极", "中性", "消极", "未分析"]
        else:
            labels = ["Positive", "Neutral", "Negative", "Unanalyzed"]

        response = {
            "labels": labels,
            "values": [
                sentiment_map["positive"],
                sentiment_map["neutral"],
                sentiment_map["negative"],
                sentiment_map["unknown"]
            ],
            "colors": ["#00c853", "#78909c", "#ff1744", "#e0e0e0"]
        }
        set_cached(cache_key, response, ttl=300)
        return response


@router.get("/sentiment-trend")
async def get_sentiment_trend(days: int = Query(default=30, le=90)):
    """获取情感趋势数据"""
    cache_key = f"charts:sentiment-trend:{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    start_date = date.today() - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT 
                DATE(date) as day,
                SUM(CASE WHEN ai_sentiment = 'positive' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN ai_sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral,
                SUM(CASE WHEN ai_sentiment = 'negative' THEN 1 ELSE 0 END) as negative
            FROM news
            WHERE date >= :start_date AND ai_sentiment IS NOT NULL
            GROUP BY DATE(date)
            ORDER BY day
        """), {"start_date": start_date})

        data = []
        for row in result:
            data.append({
                "date": str(row[0]),
                "positive": row[1],
                "neutral": row[2],
                "negative": row[3]
            })

        response = {
            "labels": [d["date"] for d in data],
            "positive": [d["positive"] for d in data],
            "neutral": [d["neutral"] for d in data],
            "negative": [d["negative"] for d in data]
        }
        set_cached(cache_key, response, ttl=600)
        return response


@router.get("/categories")
async def get_category_stats(days: int = Query(default=30, le=90)):
    """获取分类统计数据"""
    cache_key = f"charts:categories:{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    start_date = date.today() - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT category, COUNT(*) as count
            FROM news
            WHERE date >= :start_date
            GROUP BY category
            ORDER BY count DESC
            LIMIT 10
        """), {"start_date": start_date})

        categories = []
        for row in result:
            categories.append({"name": row[0], "count": row[1]})

        # 颜色配置
        colors = [
            "#1a1a2e", "#16213e", "#0f3460", "#e94560",
            "#00b894", "#fdcb6e", "#6c5ce7", "#a29bfe",
            "#fd79a8", "#55efc4"
        ]

        response = {
            "labels": [c["name"] for c in categories],
            "values": [c["count"] for c in categories],
            "colors": colors[:len(categories)]
        }
        set_cached(cache_key, response, ttl=600)
        return response


@router.get("/keywords")
async def get_keyword_trends(limit: int = Query(default=10, le=20), days: int = Query(default=30, le=90)):
    """获取关键词趋势数据"""
    cache_key = f"charts:keywords:{limit}:{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    start_date = date.today() - timedelta(days=days)

    async with async_session() as session:
        # 获取热门关键词
        top_keywords = await session.execute(text("""
            SELECT keyword, SUM(count) as total
            FROM trends
            WHERE date >= :start_date
            GROUP BY keyword
            ORDER BY total DESC
            LIMIT :limit
        """), {"start_date": start_date, "limit": limit})

        keywords = [row[0] for row in top_keywords]

        if not keywords:
            return {"labels": [], "datasets": []}

        # 获取每个关键词的趋势
        keyword_data = {}
        for keyword in keywords:
            result = await session.execute(text("""
                SELECT date, count
                FROM trends
                WHERE keyword = :keyword AND date >= :start_date
                ORDER BY date
            """), {"keyword": keyword, "start_date": start_date})

            keyword_data[keyword] = {str(row[0]): row[1] for row in result}

        # 生成日期标签
        all_dates = set()
        for data in keyword_data.values():
            all_dates.update(data.keys())
        labels = sorted(list(all_dates))

        # 生成数据集
        colors = [
            "#e94560", "#00b894", "#6c5ce7", "#fdcb6e", "#00cec9",
            "#fd79a8", "#a29bfe", "#55efc4", "#ff7675", "#74b9ff"
        ]

        datasets = []
        for i, keyword in enumerate(keywords):
            values = [keyword_data[keyword].get(d, 0) for d in labels]
            datasets.append({
                "label": keyword,
                "data": values,
                "borderColor": colors[i % len(colors)],
                "backgroundColor": colors[i % len(colors)] + "20",
                "tension": 0.3
            })

        response = {
            "labels": labels,
            "datasets": datasets
        }
        set_cached(cache_key, response, ttl=600)
        return response


@router.get("/sources")
async def get_source_stats(days: int = Query(default=30, le=90)):
    """获取来源统计数据"""
    cache_key = f"charts:sources:{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    start_date = date.today() - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT source, COUNT(*) as count
            FROM news
            WHERE date >= :start_date
            GROUP BY source
            ORDER BY count DESC
            LIMIT 15
        """), {"start_date": start_date})

        sources = []
        for row in result:
            sources.append({"name": row[0], "count": row[1]})

        response = {
            "labels": [s["name"] for s in sources],
            "values": [s["count"] for s in sources]
        }
        set_cached(cache_key, response, ttl=600)
        return response


@router.get("/regions")
async def get_region_stats(days: int = Query(default=30, le=90)):
    """获取地域分布数据"""
    cache_key = f"charts:regions:{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    start_date = date.today() - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT 
                CASE 
                    WHEN regions @> '"Americas"' THEN 'Americas'
                    WHEN regions @> '"Europe"' THEN 'Europe'
                    WHEN regions @> '"Asia-Pacific"' THEN 'Asia-Pacific'
                    WHEN regions @> '"Greater China"' THEN 'Greater China'
                    WHEN regions @> '"Middle East"' THEN 'Middle East'
                    WHEN regions @> '"EMEA"' THEN 'EMEA'
                    WHEN regions @> '"Africa"' THEN 'Africa'
                    ELSE 'Other'
                END as region,
                COUNT(*) as count
            FROM news
            WHERE date >= :start_date AND regions IS NOT NULL
            GROUP BY region
            ORDER BY count DESC
        """), {"start_date": start_date})

        regions = []
        for row in result:
            regions.append({"name": row[0], "count": row[1]})

        colors = ["#1a1a2e", "#16213e", "#0f3460", "#e94560", "#00b894", "#fdcb6e", "#6c5ce7"]

        response = {
            "labels": [r["name"] for r in regions],
            "values": [r["count"] for r in regions],
            "colors": colors[:len(regions)]
        }
        set_cached(cache_key, response, ttl=600)
        return response


@router.get("/importance")
async def get_importance_distribution(days: int = Query(default=30, le=90)):
    """获取重要性分布数据"""
    cache_key = f"charts:importance:{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    start_date = date.today() - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT 
                CASE 
                    WHEN ai_importance >= 0.8 THEN '极高 (0.8-1.0)'
                    WHEN ai_importance >= 0.6 THEN '高 (0.6-0.8)'
                    WHEN ai_importance >= 0.4 THEN '中 (0.4-0.6)'
                    WHEN ai_importance >= 0.2 THEN '低 (0.2-0.4)'
                    ELSE '极低 (0-0.2)'
                END as level,
                COUNT(*) as count
            FROM news
            WHERE date >= :start_date AND ai_importance IS NOT NULL
            GROUP BY level
            ORDER BY MIN(ai_importance) DESC
        """), {"start_date": start_date})

        levels = []
        for row in result:
            levels.append({"name": row[0], "count": row[1]})

        colors = ["#e94560", "#fdcb6e", "#00b894", "#6c5ce7", "#78909c"]

        response = {
            "labels": [l["name"] for l in levels],
            "values": [l["count"] for l in levels],
            "colors": colors[:len(levels)]
        }
        set_cached(cache_key, response, ttl=600)
        return response
