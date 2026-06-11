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
│   ├── main.py                         (FastAPI 入口)
│   ├── config.py                       (Pydantic Settings 配置)
│   ├── auth.py                         (Admin HTTP Basic Auth)
│   ├── csrf.py                         (CSRF 保护)
│   ├── cache.py                        (内存 TTL 缓存)
│   ├── i18n.py                         (国际化 zh/en)
│   ├── ai_metrics.py                   (AI 成本追踪)
│   ├── routes/
│   │   ├── api_news.py                 (新闻 CRUD、搜索、关键词)
│   │   ├── api_analysis.py             (情感、趋势、报告)
│   │   ├── api_events.py               (事件列表、详情、时间线)
│   │   ├── charts.py                   (图表数据)
│   │   ├── pages.py                    (SSR 页面路由)
│   │   └── admin.py                    (管理后台)
│   ├── templates/                      (Jinja2 模板)
│   └── static/                         (JS, CSS, 图片)
│
├── scraper/                            (数据抓取管道)
│   ├── run_news.py                     (主入口：编排完整管道)
│   ├── monitor.py                      (运行时监控)
│   ├── sources/
│   │   ├── config.yaml                 (44+ RSS 源配置)
│   │   ├── fetcher.py                  (httpx 异步抓取，SSRF 防护)
│   │   ├── rss_parser.py              (feedparser 解析)
│   │   ├── article_extractor.py       (trafilatura 正文提取)
│   │   └── api_fetcher.py             (市场数据 API)
│   ├── pipeline/
│   │   ├── classify.py                 (混合分类：关键词 + LLM)
│   │   ├── dedup.py                    (去重：link hash + n-gram + TF-IDF)
│   │   ├── keywords.py                 (关键词匹配，预编译正则)
│   │   ├── entities.py                 (实体抽取：正则 + spaCy NER)
│   │   ├── relations.py                (文章关联计算 Jaccard)
│   │   ├── events.py                   (事件检测)
│   │   ├── translate.py                (翻译 API)
│   │   ├── regions.py                  (地域提取)
│   │   ├── ai_analysis.py             (DeepSeek AI 分析)
│   │   ├── version_manager.py          (分析版本管理)
│   │   ├── retry_manager.py            (失败任务重试)
│   │   └── scheduler.py               (智能源调度)
│   └── db/
│       └── writer.py                   (两阶段写入)
│
├── deep_analyst/                       (深度分析模块，可选)
│   ├── pipeline.py                     (4步分析管道)
│   ├── knowledge.py                    (知识框架 + 因果链)
│   ├── analogy.py                      (历史类比)
│   ├── scenario.py                     (情景推演)
│   └── models/                         (知识原子、因果节点等)
│
├── models/                             (SQLAlchemy ORM 模型)
│   ├── base.py                         (异步引擎、会话)
│   ├── news.py                         (新闻表，18+ 字段)
│   ├── keyword.py                      (关键词词库)
│   ├── article_keyword.py              (文章-关键词 M2M)
│   ├── entity.py                       (命名实体)
│   ├── article_entity.py               (文章-实体 M2M)
│   ├── article_relation.py             (文章自关联)
│   ├── event.py                        (事件追踪)
│   ├── analysis.py                     (每日分析)
│   ├── daily_report.py                 (每日报告)
│   ├── trend.py                        (关键词趋势)
│   ├── source_health.py                (源健康监控)
│   ├── run_metrics.py                  (运行指标)
│   ├── market_data.py                  (市场数据)
│   ├── translation_cache.py            (翻译缓存)
│   ├── analysis_version.py             (分析版本历史)
│   ├── failed_task.py                  (失败任务队列)
│   └── schemas.py                      (Pydantic 验证)
│
├── common/                             (共享模块)
│   ├── ai_client.py                    (BaseDeepSeekClient 基类)
│   ├── mermaid.py                      (Mermaid 图表生成)
│   └── utils.py                        (文本工具、置信度计算)
│
├── alembic/                            (数据库迁移)
│   ├── env.py                          (异步 PostgreSQL 配置)
│   ├── script.py.mako                  (迁移模板)
│   └── versions/
│       └── 000_legacy.py               (基础 revision)
│
├── migrations/versions/                (Legacy SQL 迁移，历史参考)
│   ├── 001_init.sql ~ 018_seed_historical_events.sql
│
├── scripts/                            (CLI 脚本)
│   ├── stamp_migrations.py             (首次部署标记版本)
│   └── run_daily_analysis.py           (批量文章分析)
│
├── configs/                            (配置文件)
│   ├── keywords.yaml                   (1000+ 关键词，14 分类)
│   └── entities.yaml                   (实体字典)
│
├── tests/                              (测试套件)
├── docs/                               (文档)
├── alembic.ini                         (Alembic 配置)
├── pyproject.toml                      (项目配置 + 工具配置)
├── requirements.txt                    (依赖清单)
├── .env.example                        (环境变量示例)
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
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
createdb zheye

# 创建表结构（legacy SQL 迁移）
for f in migrations/versions/*.sql; do psql -U zheye -d zheye -f "$f"; done

# 标记 Alembic 版本（标记为已应用）
DATABASE_URL=postgresql+asyncpg://zheye:password@localhost:5432/zheye \
  python scripts/stamp_migrations.py

cp .env.example .env  # 编辑填入配置
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 后续更新
git pull
pip install -r requirements.txt
alembic upgrade head  # 应用数据库变更
sudo systemctl restart zheye
```

## 数据库迁移管理 (Alembic)

项目使用 Alembic 管理数据库迁移，替代手动 `psql -f` 方式。

### 目录结构

```
alembic.ini                    # 配置（从 DATABASE_URL 读取）
alembic/
├── env.py                     # 异步 PostgreSQL，导入核心 models
├── script.py.mako             # 迁移模板
└── versions/
    └── 000_legacy.py          # 基础 revision（18个legacy迁移已应用）
migrations/versions/*.sql      # 保留作为历史参考
scripts/
└── stamp_migrations.py        # 首次部署用
```

### 常用命令

```bash
# 创建迁移
alembic revision -m "描述变更内容"

# 应用所有待执行迁移
alembic upgrade head

# 回滚一步
alembic downgrade -1

# 查看当前版本
alembic current

# 查看可用版本
alembic heads
```

## 数据备份

```bash
# 每天凌晨备份数据库
0 2 * * * pg_dump zheye | gzip > /backups/zheye_$(date +\%Y\%m\%d).sql.gz

# 保留最近 7 天
0 3 * * * find /backups/ -name "*.sql.gz" -mtime +7 -delete
```
