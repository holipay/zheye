# 数据管道技术文档 (2026-06-01)

> 本文档记录 zheye 新闻抓取管道的架构演进和技术细节，供后续维护和回溯参考。

---

## 一、总体目标

将新闻抓取从"只抓 RSS 标题+摘要"升级为"全文抓取 + 结构化处理"，为 AI 分析提供更丰富的输入数据。

**核心原则：**
- 能用规则解决的不用 LLM（降低成本）
- 失败时降级而非阻塞（保证可用性）
- 复用已有能力（Fetcher 保护机制）

---

## 二、数据管道架构

### 2.1 完整流程

```
RSS Feed (22 个源)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. HTTP 抓取 (Fetcher)                                      │
│    - 随机 UA 轮换 (8 个)                                     │
│    - 域名级限速 (5-12s/请求)                                 │
│    - 并发信号量 (max 5)                                      │
│    - 失败重试 (max 2, 429 尊重 Retry-After)                  │
│    - ETag/Last-Modified 条件请求 → 304 跳过                  │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTML
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. RSS 解析 (rss_parser)                                    │
│    - feedparser 提取 title/link/summary/date                 │
│    - 日期: published_parsed → updated_parsed → None          │
└─────────────────────┬───────────────────────────────────────┘
                      │ RSS Items
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 去重 (dedup)                                             │
│    - URL SHA-256 哈希去重 (查数据库)                          │
│    - 标题模糊去重 (SequenceMatcher, 阈值 0.75)               │
└─────────────────────┬───────────────────────────────────────┘
                      │ 去重后的 Items
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 正文提取 + 日期降级                                       │
│    - fetcher.fetch_html() 复用全部 HTTP 保护                 │
│    - trafilatura 提取纯文本 (去格式/图片/广告)                │
│    - 截断 5000 字符                                          │
│    - RSS 无日期时，从 HTML <meta> 提取发表日期                │
│    - 每次提取后等待 2-5s                                      │
└─────────────────────┬───────────────────────────────────────┘
                      │ Items + content + pub_date
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 分类 + 类型 + 地域                                        │
│    - classify_by_keywords: 关键词→类别 (13 个分类)           │
│    - detect_article_type: news/opinion/analysis/data         │
│    - extract_regions: 涉及的大区 (Americas/Europe/...)       │
└─────────────────────┬───────────────────────────────────────┘
                      │ 结构化 Items
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. 存入 DB (writer.save_news)                               │
│    - INSERT ... ON CONFLICT DO NOTHING                       │
│    - 关键词匹配 → article_keywords 表                        │
│    - 实体提取 → entities + article_entities 表               │
│    - 文章关联 → article_relations 表 (Jaccard ≥ 0.3)        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 批次控制

```
22 个源 → 打乱顺序 → 分 5 批 (BATCH_SIZE=5)
                        ↓
        批次1 (5个源) → 等待 15-40s
        批次2 (5个源) → 等待 15-40s
        ...
        批次5 (2个源)
```

---

## 三、数据库 Schema

### 3.1 核心表

```sql
-- 新闻表
news (
    id, title, translated_title, link, link_hash,
    source, category, lang,
    summary,            -- RSS 摘要
    content,            -- 正文纯文本 (新增)
    article_type,       -- news/opinion/analysis/data (新增)
    regions,            -- JSONB 地域数组 (新增)
    date,               -- 发表日期
    created_at          -- 入库时间
)

-- 实体表 (新增)
entities (
    id, name, entity_type, normalized_name, created_at
)

-- 文章-实体关联表 (新增)
article_entities (
    id, article_id→news, entity_id→entities,
    context, relevance, created_at
)

-- 关键词表
keywords (id, term, lang, category, weight)

-- 文章-关键词关联表
article_keywords (id, article_id, keyword_id, relevance)

-- 文章关联表
article_relations (id, source_id, target_id, relation_type, score)

-- 源健康监控
source_health (
    ..., last_etag, last_rss_modified  -- 新增: 缓存条件请求头
)
```

### 3.2 迁移脚本

| 文件 | 内容 |
|------|------|
| `001_init.sql` | 基础表 (news, analyses, source_health, etc.) |
| `002_add_keywords.sql` | keywords, article_keywords, article_relations |
| `003_add_content.sql` | news.content, source_health.last_etag/last_rss_modified |
| `004_add_entities.sql` | entities, article_entities, news.article_type/regions |

---

## 四、新增模块详解

### 4.1 正文提取 (`scraper/sources/article_extractor.py`)

**两个函数：**

| 函数 | 用途 |
|------|------|
| `extract_article(url, html)` | 同步版，trafilatura 直接抓取（未使用） |
| `extract_article_from_html(url, html)` | 接受预抓取的 HTML，纯提取 |
| `extract_date_from_html(url, html)` | 从 HTML 元数据提取发表日期 |

**trafilatura 配置：**
- `include_comments=False` — 去除评论
- `include_tables=True` — 保留表格（含数据）
- `output_format='txt'` — 纯文本输出

**文本清洗：**
- 合并多余空白为单空格
- 合并 3+ 连续换行为双换行
- 截断 5000 字符

### 4.2 实体提取 (`scraper/pipeline/entities.py`)

**实体类型：**

| 类型 | 来源 | 示例 |
|------|------|------|
| company | `configs/entities.yaml` 词库 | Apple, 特斯拉, 阿里巴巴 |
| indicator | `configs/entities.yaml` 词库 | GDP, CPI, PMI |
| organization | `configs/entities.yaml` 词库 | 美联储, ECB, IMF |
| country | `configs/entities.yaml` 词库 | 美国, 中国, 欧盟 |
| currency | 正则匹配 | $394 billion, ¥500亿 |
| percentage | 正则匹配 | 5.25%, 3% |
| basis_point | 正则匹配 | 25bp, 100bps |

**匹配策略：**
- 公司/机构：`\b` 词边界匹配（避免误匹配子串）
- 指标/国家：子串匹配（"GDP" 出现在任何位置即匹配）
- 数字实体：正则匹配 + 去重重叠（`$394 billion` 不会重复匹配 `$394`）
- 每个实体附带上下文片段 (context, ±30 字符)

**词库规模：** 50+ 公司、12 指标、13 组织、14 国家

### 4.3 文章类型检测 (`scraper/pipeline/classify.py: detect_article_type`)

**信号词匹配，不依赖 LLM：**

| 类型 | 信号词示例 |
|------|-----------|
| opinion | opinion, editorial, commentary, 观点, 评论, 专栏 |
| analysis | analysis, outlook, forecast, deep dive, 分析, 展望, 深度 |
| data | report, statistics, earnings report, 报告, 数据, 季报 |
| news | 默认类型（无信号词命中时） |

**检测范围：** 标题 + 摘要（标题权重更高，因为信号词通常在标题中）

### 4.4 地域标记 (`scraper/pipeline/regions.py`)

**映射链路：** 国家/地区名 → 大区

| 大区 | 包含国家/地区 |
|------|-------------|
| Americas | US, U.S., 美国, Canada, 巴西 |
| Europe | UK, EU, 欧盟, 德国, 法国 |
| Asia-Pacific | 日本, 韩国, 印度, 澳大利亚 |
| Greater China | 中国, 香港, 台湾 |
| Middle East | 中东, 沙特, UAE |
| EMEA | 俄罗斯 |
| Africa | 非洲 |

**匹配逻辑：**
- 含 `.` 的短词 (如 `U.S.`)：用 `(?<![a-zA-Z])...\(?![a-zA-Z])` 边界匹配
- 其他：子串匹配
- 检测范围：标题 + 摘要 + 正文

---

## 五、反爬保护机制

### 5.1 Fetcher 层 (`scraper/sources/fetcher.py`)

| 机制 | 参数 | 说明 |
|------|------|------|
| UA 轮换 | 8 个 UA | 每次请求随机选择 |
| 域名限速 | 5-12s/域 | 同域名请求间隔 |
| 并发控制 | max 5 | 信号量限制 |
| 失败重试 | max 2 | 1-4s 退避 |
| 429 处理 | Retry-After | 尊重服务端限流 |
| 条件请求 | ETag/Last-Modified | 304 时跳过 |

### 5.2 正文抓取层

| 机制 | 参数 | 说明 |
|------|------|------|
| 复用 Fetcher | fetch_html() | 享受全部 HTTP 保护 |
| 请求间隔 | 2-5s | 每次正文提取后等待 |
| 批次间隔 | 15-40s | RSS 源批次之间 |

### 5.3 请求流程

```
单个源的请求时序:
  RSS 请求 (域名限速 5-12s)
    → 解析条目
    → 文章1 HTML (域名限速 5-12s) → 提取正文 → 等待 2-5s
    → 文章2 HTML (域名限速 5-12s) → 提取正文 → 等待 2-5s
    → ...
```

---

## 六、关键词匹配 (`scraper/pipeline/keywords.py`)

**匹配权重策略：**

| 匹配位置 | 同分类 relevance | 跨分类 relevance |
|----------|-----------------|-----------------|
| 标题/摘要 | weight × 1.0 | weight × 0.8 |
| 正文 | weight × 0.5 | weight × 0.4 |

**匹配规则：**
- 英文：`\b` 词边界正则匹配，≥ 3 字符
- 中文：精确子串匹配，≥ 2 字
- 词库：`configs/keywords.yaml` (268 个专业术语)

---

## 七、文件清单

### 新增文件

| 文件 | 用途 |
|------|------|
| `scraper/pipeline/entities.py` | 实体提取模块 |
| `scraper/pipeline/regions.py` | 地域标记模块 |
| `models/entity.py` | Entity 模型 |
| `models/article_entity.py` | ArticleEntity 模型 |
| `configs/entities.yaml` | 实体词库 |
| `migrations/versions/003_add_content.sql` | content + 条件请求字段 |
| `migrations/versions/004_add_entities.sql` | 实体表 + article_type + regions |

### 修改文件

| 文件 | 改动 |
|------|------|
| `models/news.py` | 新增 content, article_type, regions 字段 |
| `models/source_health.py` | 新增 last_etag, last_rss_modified 字段 |
| `scraper/sources/fetcher.py` | 新增 fetch_html() 方法 |
| `scraper/sources/article_extractor.py` | 重写: extract_article_from_html + extract_date_from_html |
| `scraper/sources/__init__.py` | 更新导出 |
| `scraper/pipeline/classify.py` | 新增 detect_article_type() |
| `scraper/pipeline/keywords.py` | 支持 content 参数，分级权重 |
| `scraper/run_news.py` | 集成正文提取/日期降级/类型检测/地域标记 |
| `scraper/db/writer.py` | 集成实体存储，支持条件请求头 |

---

## 八、待办事项

| 优先级 | 功能 | 说明 |
|--------|------|------|
| 中 | 内容摘要 | LLM 将正文压缩为 2-3 句，降低 AI 分析成本 |
| 中 | 情感立场 | LLM 判断看涨/看跌/中性，支持趋势分析 |
| 低 | 动态标签 | 自动提取高频新词，发现新话题 |
| 低 | 翻译集成 | 翻译标题为中文，已弃用 (translate.py 存在但未调用) |

---

## 九、部署清单

```bash
# 1. 拉取代码
git pull

# 2. 安装依赖
pip install -r requirements.txt

# 3. 执行数据库迁移
psql zheye < migrations/versions/003_add_content.sql
psql zheye < migrations/versions/004_add_entities.sql

# 4. 重启服务
sudo systemctl restart zheye
```
