# zheye — 全球新闻聚合与 AI 分析平台

## 项目定位

| 维度 | 定义 |
|------|------|
| 目标 | 全球金融、科技、社科新闻聚合 + AI 深度分析 |
| 用户规模 | 10万 PV/天 |
| 数据源 | 50+ RSS/API 源 |
| 更新频率 | 每天 2 次 |
| 部署 | 海外虚拟主机（抓取便利） |

## 技术栈

```
抓取层    feedparser + httpx + beautifulsoup4 + trafilatura
处理层    翻译 API (MyMemory/Google/DeepSeek) + DeepSeek API (AI 分析)
存储层    PostgreSQL + SQLAlchemy + Alembic
Web 层    FastAPI + Jinja2 (服务端渲染) + HTMX (前端交互)
调度层    APScheduler 或 Cron
部署层    Nginx + Uvicorn + Systemd + Cloudflare CDN
```

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                       Cloudflare (免费)                       │
│                 CDN + SSL + DDoS 防护                         │
└─────────────────────────┬────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────┐
│                     虚拟主机 (海外)                            │
│                                                               │
│   Nginx (:80/:443)                                            │
│     ├── /static/*  → 直接返回文件                              │
│     └── /*         → proxy_pass :8000 (FastAPI)               │
│                                                               │
│   Uvicorn (:8000) — Systemd 管理                              │
│     └── FastAPI 应用                                          │
│                                                               │
│   PostgreSQL                                                  │
│     └── zheye 数据库                                          │
│                                                               │
│   Cron Jobs                                                   │
│     ├── 0 0 * * *  python scraper/run_news.py && python ...  │
│     └── 0 12 * * * python scraper/run_news.py                │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## 工作流

```
开发环境 (本地)     git push      GitHub (代码仓库)
     ─────────────────────────────→
                                        │
                                   git pull
                                        │
                                  虚拟主机 (运营环境)
                                  Python + PostgreSQL + Nginx + Cron
```

- GitHub 只存代码，不运行任何东西
- 虚拟主机拉取代码，配合运行环境实际运营
- 数据存储在 PostgreSQL，不进 Git

## 目录结构

```
zheye/
│
├── app/                                (Web 应用)
│   ├── __init__.py
│   ├── main.py                         (FastAPI 入口)
│   ├── config.py                       (配置管理)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py                    (页面路由: / /news /articles)
│   │   └── api.py                      (HTMX API: /api/news /api/analysis)
│   ├── templates/                      (Jinja2 模板)
│   │   ├── base.html                   (公共布局)
│   │   ├── index.html                  (AI 分析页)
│   │   ├── news.html                   (新闻列表页)
│   │   ├── articles.html               (文章页)
│   │   └── partials/                   (HTMX 片段)
│   │       ├── news_list.html
│   │       ├── news_sidebar.html
│   │       └── analysis_card.html
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── htmx.min.js
│   └── cache.py                        (内存缓存)
│
├── scraper/                            (数据管道)
│   ├── __init__.py
│   ├── run_news.py                     (抓取入口)
│   ├── run_analyze.py                  (分析入口)
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── config.yaml                 (源列表配置)
│   │   ├── fetcher.py                  (HTTP 抓取)
│   │   ├── rss_parser.py              (RSS/Atom 解析)
│   │   └── article_extractor.py       (正文提取)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── translate.py                (翻译管道)
│   │   ├── dedup.py                    (去重: URL + 标题相似度)
│   │   ├── classify.py                 (分类: 关键词 + LLM)
│   │   └── analyze.py                  (AI 深度分析)
│   └── db/
│       ├── __init__.py
│       └── writer.py                   (数据写入)
│
├── models/                             (数据模型)
│   ├── __init__.py
│   ├── base.py                         (SQLAlchemy 引擎)
│   ├── news.py                         (新闻表)
│   ├── analysis.py                     (分析表)
│   ├── translation_cache.py            (翻译缓存)
│   ├── source_health.py                (源健康监控)
│   └── run_metrics.py                  (运行指标)
│
├── migrations/                         (数据库迁移)
│   └── versions/
│       └── 001_init.sql
│
├── configs/                            (配置文件)
│   ├── daily_perspectives.json         (每日分析视角)
│   ├── noise_keywords.json             (噪音关键词)
│   ├── domain_keywords.json            (领域关键词)
│   ├── source_weights.json             (源权重)
│   └── stopwords.json                  (停用词)
│
├── tests/                              (测试)
│   ├── test_scraper.py
│   ├── test_dedup.py
│   └── test_api.py
│
├── logs/                               (日志，不进 Git)
│
├── .env                                (环境变量，不进 Git)
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile                          (可选)
├── docker-compose.yml                  (可选)
└── README.md
```

## 数据库设计 (PostgreSQL)

```sql
-- 新闻表
CREATE TABLE news (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    translated_title VARCHAR(500),
    link VARCHAR(1000) NOT NULL,
    link_hash VARCHAR(64) NOT NULL,
    source VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    lang VARCHAR(10) DEFAULT 'en',
    summary TEXT,
    date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_link_hash UNIQUE (link_hash)
);

CREATE INDEX idx_news_category_date ON news (category, date DESC);
CREATE INDEX idx_news_source ON news (source);
CREATE INDEX idx_news_created ON news (created_at DESC);
CREATE INDEX idx_news_fts ON news USING gin (
    to_tsvector('simple', title || ' ' || COALESCE(translated_title, ''))
);

-- 分析表
CREATE TABLE analyses (
    id BIGSERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    analysis TEXT NOT NULL,
    structured JSONB,
    hot_keywords JSONB,
    perspective VARCHAR(50),
    news_count INT DEFAULT 0,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analyses_date ON analyses (date DESC);
CREATE INDEX idx_analyses_keywords ON analyses USING gin (hot_keywords);

-- 翻译缓存
CREATE TABLE translation_cache (
    id BIGSERIAL PRIMARY KEY,
    source_text VARCHAR(1000) NOT NULL,
    translated_text VARCHAR(1000) NOT NULL,
    source_hash VARCHAR(64) UNIQUE NOT NULL,
    provider VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_translation_hash ON translation_cache (source_hash);

-- 源健康监控
CREATE TABLE source_health (
    id BIGSERIAL PRIMARY KEY,
    source_name VARCHAR(100) UNIQUE NOT NULL,
    total_checks INT DEFAULT 0,
    total_success INT DEFAULT 0,
    total_failure INT DEFAULT 0,
    consecutive_failures INT DEFAULT 0,
    last_check TIMESTAMPTZ,
    last_success TIMESTAMPTZ,
    last_error TEXT,
    last_items INT DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0
);

-- 运行指标
CREATE TABLE run_metrics (
    id BIGSERIAL PRIMARY KEY,
    run_type VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    duration_seconds INT,
    sources_attempted INT DEFAULT 0,
    sources_succeeded INT DEFAULT 0,
    sources_failed INT DEFAULT 0,
    items_fetched INT DEFAULT 0,
    items_deduped INT DEFAULT 0,
    items_final INT DEFAULT 0,
    translate_cached INT DEFAULT 0,
    translate_new INT DEFAULT 0,
    translate_failed INT DEFAULT 0,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metrics_type ON run_metrics (run_type, started_at DESC);

-- 趋势数据
CREATE TABLE trends (
    id BIGSERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    keywords JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 事件链
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500),
    description TEXT,
    category VARCHAR(50),
    first_seen DATE,
    last_updated DATE,
    update_count INT DEFAULT 1,
    status VARCHAR(20) DEFAULT 'active',
    data JSONB
);

CREATE INDEX idx_events_status ON events (status, last_updated DESC);
```

## API 路由设计

### 页面路由 (服务端渲染)

| 路由 | 说明 |
|------|------|
| `GET /` | AI 分析页（首页） |
| `GET /news?category=xxx` | 新闻列表页 |
| `GET /articles` | 文章页 |

### HTMX API (返回 HTML 片段)

| 路由 | 参数 | 说明 |
|------|------|------|
| `GET /api/news` | `category`, `page` | 切换分类/翻页 |
| `GET /api/analysis/{date}` | `date` | 加载指定日期分析 |
| `GET /api/search` | `q`, `page` | 全文搜索 |
| `GET /api/meta` | — | 分类元数据 |
| `GET /api/latest` | — | 最新新闻 JSON |

## 源配置格式

```yaml
# scraper/sources/config.yaml

sources:
  - name: Reuters
    type: rss
    url: https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best
    lang: en
    category: 国际财经
    weight: 2.0

  - name: Bloomberg
    type: rss
    url: https://feeds.bloomberg.com/markets/news.rss
    lang: en
    category: 股市与市场
    weight: 2.0

  # ... 更多源

settings:
  fetch_timeout: 20
  max_retries: 2
  dedup_threshold: 0.75
  retention_days: 30
  max_items_per_category: 40
```

## 抓取管道流程

```
run_news.py 入口
│
├── 1. 加载 config.yaml 源列表
├── 2. 并发抓取 (asyncio + httpx)
│     ├── RSS 源 → feedparser 解析
│     ├── API 源 → 对应 parser
│     └── ETag/Last-Modified 增量抓取
├── 3. 预处理
│     ├── URL 去重 (查数据库 link_hash)
│     ├── 中文条目 → 直接模糊去重
│     └── 英文条目 → 翻译 → 模糊去重
├── 4. 分类 (关键词匹配 + LLM 辅助)
├── 5. 写入数据库
├── 6. 清理旧数据 (retention_days: 30)
└── 7. 记录 run_metrics
```

## AI 分析流程

```
run_analyze.py 入口
│
├── 1. 加载当日新闻
├── 2. 提取热词 (TF-IDF + 频率 + 跨分类覆盖)
├── 3. 筛选 Top 50 新闻
├── 4. 抓取文章正文 (trafilatura)
├── 5. 加载历史分析记忆
├── 6. 调用 DeepSeek API
│     ├── 提取结构化信号 (情感、风险、主题)
│     └── 生成深度分析
├── 7. 写入 analyses 表
└── 8. 更新 trends 表
```

## 缓存策略

```
L1 浏览器     HTTP Cache-Control (页面 5分钟, 静态 7天)
L2 CDN        Cloudflare 边缘缓存 (页面 5分钟, 静态 7天)
L3 应用层     Python 内存缓存 (cachetools, TTL 2-5分钟)
L4 数据库     PostgreSQL 共享缓冲区 + 连接池
```

## 依赖清单

```
# Web
fastapi, uvicorn[standard], jinja2, python-multipart

# 数据库
sqlalchemy[asyncio], asyncpg, alembic

# 抓取
feedparser, httpx, beautifulsoup4, lxml, trafilatura

# AI
openai (DeepSeek 兼容)

# 工具
cachetools, python-dotenv, pyyaml, apscheduler

# 测试
pytest, pytest-asyncio
```

## 部署步骤

```bash
# 初始部署
git clone https://github.com/holipay/zheye.git
cd zheye
pip install -r requirements.txt
createdb zheye
psql zheye < migrations/001_init.sql
cp .env.example .env  # 编辑填入配置
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 后续更新
git pull
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart zheye
```

## 数据备份

```bash
# 每天凌晨备份数据库
0 2 * * * pg_dump zheye | gzip > /backups/zheye_$(date +\%Y\%m\%d).sql.gz

# 保留最近 7 天
0 3 * * * find /backups/ -name "*.sql.gz" -mtime +7 -delete
```
