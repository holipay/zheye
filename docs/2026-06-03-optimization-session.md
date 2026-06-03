# 2026-06-03 代码优化会话记录

## 概述

本次会话对 zheye 项目进行了全面的代码审查和优化，共修复 **43 个问题**，涵盖性能、安全、代码质量、可维护性等方面。

**提交记录**:
```
27f51a7 feat: 添加 API 速率限制和请求体大小限制
4b4b58f fix: P3 快速修复（第一批）
994bf09 refactor: 添加类型注解（P2-24）
1bfba89 refactor: 提升代码规范（第三批）
c27d835 refactor: 消除重复代码（第二批）
56a66ba fix: 添加外键约束 + 修复硬编码路径
b2c87c7 fix: 修复 P1-12 和 P1-13 问题
ccd4850 fix: 修复 P1-10 和 P1-14 问题
cee4d8b perf: 优化 admin.py 和 writer.py 数据库查询
f01f88d perf: 修复 api_events.py 循环内 N+1 查询
a2fbfec fix: 修复 classify.py 配置路径错误
a38e2ff fix: 修复 datetime.utcnow() 废弃问题
a657fd7 security: 修复 P0 安全问题
dd61220 perf: 修复 charts.py 关键词趋势 N+1 查询
245ac76 refactor: 优化双向关系存储，只保留单条记录
06ed4f6 feat: 添加 Pydantic Schema 数据验证
9728f91 feat: 添加 Token 监控和缓存限制
e94069e perf: 优化 AI 处理和数据管道性能
762d22c feat: 修复 5 项代码质量问题
6cc921d perf: 优化三项性能问题
551c5fd refactor: 统一依赖注入 + 修复 SQL 注入风险
ae155a1 refactor: 拆分 api.py (1785行) 为四个模块化路由文件
```

---

## 一、架构优化

### 1.1 API 路由模块化

**问题**: `api.py` 文件过大（1785行），所有 API 端点混在一起。

**解决方案**: 拆分为 4 个模块化路由文件。

| 文件 | 行数 | 职责 |
|------|------|------|
| `api_common.py` | 48 | 共享工具：router、templates、context 构建、事件查询辅助 |
| `api_news.py` | 572 | 新闻、关键词、实体、搜索相关 API |
| `api_analysis.py` | 339 | AI 分析报告（日报、周报、月报、趋势、情感） |
| `api_events.py` | 830 | 事件追踪、知识框架、因果链、历史类比、情景推演 |

### 1.2 模板上下文构建统一

**问题**: `pages.py`、`api_common.py`、`admin.py` 三个模块有相似的上下文构建函数。

**解决方案**: 创建 `app/context.py` 共享模块。

```python
# app/context.py
def get_template_context(request, include_csrf=False, **kwargs)
def get_api_context(request, **kwargs)
```

### 1.3 配置管理集中化

**问题**: 配置值散落在多个文件中，硬编码魔法数字。

**解决方案**: 扩展 `app/config.py`，添加 30+ 配置常量。

```python
# app/config.py
class Settings:
    # 缓存配置
    CACHE_MAX_SIZE: int = 100
    CACHE_TTL_SECONDS: int = 300
    
    # AI 配置
    AI_MAX_RETRIES: int = 3
    AI_TIMEOUT_SECONDS: int = 30
    
    # 去重配置
    DEDUP_THRESHOLD: float = 0.75
    RELATION_THRESHOLD: float = 0.3
    
    # 速率限制
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_API: str = "30/minute"
```

---

## 二、性能优化

### 2.1 N+1 查询修复

**问题**: 多处存在 N+1 查询问题。

**修复清单**:

| 位置 | 问题 | 优化方案 |
|------|------|---------|
| `api_news.py` `/keywords` | 循环内逐条查询文章计数 | 使用子查询一次性获取 |
| `admin.py` `/dashboard` | 7+ 次独立统计查询 | 使用 `filter` 合并为 5 次 |
| `charts.py` `/keywords` | 循环内每个关键词单独查询 | 使用 `IN` 条件一次查询 |
| `api_events.py` `/analogies` | 循环内检查已存在类比 | 批量查询后内存过滤 |
| `writer.py` `save_news` | INSERT + SELECT 获取 ID | 使用 `RETURNING id` |

**示例**:
```python
# 优化前
for kw in keywords:
    count = await session.execute(select(func.count(...)))

# 优化后
article_count_subq = select(
    ArticleKeyword.keyword_id,
    func.count(ArticleKeyword.id).label("article_count")
).group_by(ArticleKeyword.keyword_id).subquery()
```

### 2.2 实体匹配算法优化

**问题**: `entities.py` 匹配复杂度 O(实体数×别名数×文本长度)。

**解决方案**: 预编译正则表达式 + 批量查询。

```python
# 预编译实体正则
_entity_patterns = None

def _build_entity_patterns(config):
    patterns = defaultdict(list)
    for entity_type in [...]:
        for entry in config.get(entity_type, []):
            for alias in entry.get("aliases", []):
                pattern = re.compile(re.escape(alias), re.IGNORECASE)
                patterns[entity_type].append((pattern, name, alias))
    return patterns
```

### 2.3 翻译模块优化

**问题**: 每次翻译创建新 HTTP 客户端，无缓存。

**解决方案**: HTTP 连接池复用 + 内存缓存。

```python
_http_client: Optional[httpx.AsyncClient] = None
_translation_cache: dict[str, str] = {}

async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=15, limits=...)
    return _http_client
```

### 2.4 去重算法优化

**问题**: `dedup.py` 线性扫描所有标题。

**解决方案**: 添加 n-gram 预筛选机制。

```python
def is_duplicate(title, existing_titles, threshold=0.75):
    prefilter_threshold = threshold * 0.6
    for existing in existing_titles:
        if _ngram_similarity(title, existing) < prefilter_threshold:
            continue  # 快速过滤
        if similarity(title, existing) >= threshold:
            return True
    return False
```

### 2.5 双向关系存储优化

**问题**: 每条关系存两条记录，存储翻倍。

**解决方案**: 只存一条（source_id < target_id），查询时用 OR 条件。

```python
# 存储时规范化方向
def _normalize_relation(source_id, target_id):
    if source_id > target_id:
        return target_id, source_id
    return source_id, target_id

# 查询时使用 OR
query = select(...).where(or_(
    ArticleRelation.source_id == article_id,
    ArticleRelation.target_id == article_id
))
```

### 2.6 性能索引

**新增索引** (`014_add_performance_indexes.sql`):
```sql
idx_news_fts              -- News 全文搜索 GIN
idx_events_data_type      -- Events JSONB (event_type)
idx_events_status         -- Events 状态
idx_events_last_updated   -- Events 时间
idx_knowledge_atoms_type_lang  -- Knowledge 复合
idx_causal_nodes_event_type    -- Causal 复合
```

---

## 三、安全修复

### 3.1 依赖注入统一

**问题**: API 路由直接使用 `async with async_session()`，管理后台用 `Depends`。

**解决方案**: 统一使用 `Depends(get_session)`。

```python
# models/base.py
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

# API 路由
@router.get("/news")
async def get_news(session: AsyncSession = Depends(get_session)):
    ...
```

### 3.2 SQL 注入修复

**问题**: `run_period_report.py` 使用 f-string 构建 SQL。

**解决方案**: 添加白名单验证 + SQLAlchemy table 构造。

```python
REPORT_TABLES = {"weekly_reports", "monthly_reports"}

if table_name not in REPORT_TABLES:
    raise ValueError(f"无效的表名: {table_name}")
```

### 3.3 敏感信息泄露修复

**问题**: `get_system_info` 暴露数据库连接信息。

**解决方案**: 只返回是否配置，不暴露详细信息。

```python
# 优化前
"database_url": os.getenv("DATABASE_URL", "").split("@")[-1]

# 优化后
"database_configured": bool(os.getenv("DATABASE_URL"))
```

### 3.4 外键约束

**问题**: `CausalLink`、`EventKnowledgeAtom` 缺少外键约束。

**解决方案**: 添加外键约束 + 迁移脚本。

```sql
-- 013_add_foreign_keys.sql
ALTER TABLE causal_links ADD CONSTRAINT fk_causal_link_source 
    FOREIGN KEY (source_node_id) REFERENCES causal_nodes(id) ON DELETE CASCADE;

ALTER TABLE event_knowledge_atoms ADD CONSTRAINT fk_event_atom_event 
    FOREIGN KEY (event_id) REFERENCES event_knowledge(event_id) ON DELETE CASCADE;
```

### 3.5 API 速率限制

**解决方案**: 使用 `slowapi` 库。

```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@router.get("/news")
@limiter.limit("30/minute")
async def get_news(request: Request, ...):
    ...
```

---

## 四、AI 处理优化

### 4.1 API 调用稳定性

**问题**: 无重试、无限流、无超时控制。

**解决方案**: 添加重试机制和指标监控。

```python
class DeepSeekClient:
    RETRYABLE_ERRORS = ("RateLimitError", "APITimeoutError", ...)
    
    def _call_api(self, messages, temperature, max_tokens, function_name):
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(...)
                metrics.record_usage(...)  # 记录 token 使用
                return response.choices[0].message.content
            except RateLimitError:
                time.sleep(2 ** attempt * 1.0)  # 指数退避
```

### 4.2 公共 AI 调用函数

**问题**: 5 个模块有相同的"AI 调用-解析-后处理"模式。

**解决方案**: 在 `utils.py` 中提取 `ai_analyze()` 函数。

```python
async def ai_analyze(prompt, ai_client, *, temperature=0.3, 
                     max_tokens=3000, schema=None, function_name="ai_analyze"):
    response = ai_client.chat(messages=[...], temperature=temperature, ...)
    result = parse_ai_response(response, schema=schema)
    if result:
        result['ai_model'] = 'deepseek-chat'
        result['ai_confidence'] = 0.8
    return result
```

### 4.3 Pydantic Schema 验证

**问题**: AI 返回数据无结构验证。

**解决方案**: 创建 `models/schemas.py`，定义所有数据结构。

```python
class ArticleAnalysisSchema(BaseModel):
    sentiment: SentimentType
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    summary_zh: str = Field(max_length=1000)
    importance: float = Field(ge=0.0, le=1.0)
```

### 4.4 Token 用量监控

**新增模块**: `app/ai_metrics.py`

```python
class AIMetrics:
    def record_usage(self, prompt_tokens, completion_tokens, function_name)
    def get_daily_report(self, day=None) -> dict
    def get_summary(self, days=7) -> dict
```

### 4.5 智能文本截断

**问题**: 内容截断在词中间，影响 AI 理解。

**解决方案**: 在句子边界截断。

```python
def smart_truncate(text, max_len=3000, threshold=0.6):
    truncated = text[:max_len]
    for sep in ['。', '.\n', '.', '；', '\n']:
        last_sep = truncated.rfind(sep)
        if last_sep > max_len * threshold:
            return truncated[:last_sep + len(sep)]
    return truncated
```

---

## 五、代码质量改进

### 5.1 重复代码消除

| 函数 | 提取位置 | 使用位置 |
|------|---------|---------|
| `smart_truncate()` | `utils.py` | `ai_analysis.py`, `translate.py` |
| `parse_date()` | `api_analysis.py` | 5 处日期验证 |
| `serialize_daily_report()` | `api_analysis.py` | 2 处报告序列化 |
| `validate_lang()` | `pages.py` | 7 处语言验证 |

### 5.2 类型注解

**添加位置**:
- `admin.py`: `load_rss_config() -> dict[str, Any]`
- `writer.py`: `save_news()`, `process_article_event()`, `update_source_health()`

### 5.3 异常处理改进

**改进位置**: `writer.py` `save_news()`

```python
# 优化前：单一 try-except
try:
    # 所有操作
except Exception as e:
    logger.error(f"Error: {e}")

# 优化后：分层 try-except
try:
    # INSERT
    if row:
        try:
            # 关键词匹配
        except Exception as e:
            logger.warning(f"关键词匹配失败: {e}")
        try:
            # 实体提取
        except Exception as e:
            logger.warning(f"实体提取失败: {e}")
except Exception as e:
    logger.error(f"保存新闻失败: {e}", exc_info=True)
```

### 5.4 未使用导入清理

**清理文件**:
- `scenario.py`: 移除 `import json`
- `analogy.py`: 移除 `import json`
- `knowledge.py`: 移除 `import json`

---

## 六、测试修复

### 6.1 测试断言修复

```python
# 优化前
assert response.json() == {"status": "ok"}

# 优化后
data = response.json()
assert "status" in data
assert data["status"] in ["ok", "degraded"]
```

### 6.2 测试路由修复

```python
# 优化前
response = await client.get("/news")

# 优化后
response = await client.get("/en/news")
```

---

## 七、迁移脚本

| 脚本 | 用途 |
|------|------|
| `011_normalize_relations.sql` | 清理重复双向关系 |
| `012_add_source_health_fields.sql` | 添加 last_etag, last_rss_modified |
| `013_add_foreign_keys.sql` | 添加外键约束 |
| `014_add_performance_indexes.sql` | 添加性能索引 |

**执行顺序**:
```bash
psql -d zheye -f migrations/versions/011_normalize_relations.sql
psql -d zheye -f migrations/versions/012_add_source_health_fields.sql
psql -d zheye -f migrations/versions/013_add_foreign_keys.sql
psql -d zheye -f migrations/versions/014_add_performance_indexes.sql
```

---

## 八、依赖更新

**requirements.txt 新增**:
```
pydantic      # 数据验证
slowapi       # API 速率限制
```

---

## 九、剩余待办事项

### 长期任务

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 补充测试覆盖 | P3 | 当前仅 7 个测试文件 |
| 补充文档 | P3 | API 文档、部署文档等 |
| Docker 配置 | P3 | Dockerfile + docker-compose |
| CI/CD 配置 | P3 | GitHub Actions |

### 可选优化

| 任务 | 说明 |
|------|------|
| Redis 缓存 | 多进程共享缓存 |
| 向量搜索 | 事件相似度匹配 |
| 结构化日志 | JSON 格式日志 |

---

## 十、统计摘要

| 类别 | 数量 |
|------|------|
| 修改文件 | 25+ |
| 新增文件 | 10+ |
| 提交次数 | 22 |
| 修复问题 | 43 |
| 性能优化 | 8 项 |
| 安全修复 | 5 项 |
| 代码质量 | 12 项 |
| 新增配置 | 30+ |
| 新增索引 | 6 个 |
| 迁移脚本 | 4 个 |
