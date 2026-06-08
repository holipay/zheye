# 数据管道深度修复：事务回滚与两阶段架构重构

**日期**: 2026-06-08
**问题**: RSS 抓取数据持续丢失（6月1日至今，每次运行都失败）
**严重程度**: 高（连续 8 天数据完全缺失，日志显示成功但实际 0 入库）
**修复提交**: `84f6eba`

---

## 1. 问题描述

运行 `check_pipeline.py` 发现：

```
[FAIL] 最近2小时入库数据: 0 条
[FAIL] 运行 2026-06-08 06:00: 指标显示保存 756 条, 实际入库 0 条
[FAIL] 最近48小时无数据
[WARN] 11 个源连续失败 >= 3 次
```

数据库状态：
- 总数据量：227 条
- 最后一条数据：`2026-05-31 10:38:02`
- 6月1日之后的数据：0 条

但 RunMetrics 记录显示每次运行都"成功"保存了 700-800 条文章。

---

## 2. 诊断过程

### 2.1 关键日志发现

```bash
grep "数据校验失败" logs/scraper.log | head -5

# 输出：
# 2026-06-07 22:29:09 [ERROR] 数据校验失败: 预期 805 条, 实际入库 0 条
# 2026-06-08 00:29:05 [ERROR] 数据校验失败: 预期 823 条, 实际入库 0 条
# ... 每次运行都失败
```

每次运行后校验都失败：INSERT RETURNING 返回了 756 条，但 commit 后数据库中实际为 0 条。

### 2.2 定位根因

```bash
grep -B5 "数据校验失败" logs/scraper.log

# 关键发现：
# [WARNING] 实体同步失败: StatementTooComplexError: stack depth limit exceeded
# [ERROR] 数据校验失败: 预期 756 条, 实际入库 0 条
```

**每次失败前都有 `StatementTooComplexError`**。

### 2.3 错误详情

```
(sqlalchemy.dialects.postgresql.asyncpg.Error)
<class 'asyncpg.exceptions.StatementTooComplexError'>: stack depth limit exceeded

parameters: ('christine lagarde: women', 'person', 'speech', 'organization',
'christine lagarde', 'person', 'ecb', 'organization', ...
... 19798 parameters truncated ...)
```

SQL 参数数量约 20000 个，超出 PostgreSQL 的 `stack_depth` 限制。

---

## 3. 根因分析

### 3.1 故障链路

```
NER 从 756 篇文章提取大量实体
         ↓
sync_entities_to_db() 构造 tuple_(...).in_(keys) 查询
         ↓
keys 数量过大（数千个），生成 ~20000 个 SQL 参数
         ↓
PostgreSQL 报错: StatementTooComplexError
         ↓
PostgreSQL 事务进入 aborted 状态
         ↓
try/except 捕获 Python 异常，但 PG 事务仍然 aborted
         ↓
session.commit() 检测到 aborted → 实际执行 ROLLBACK
         ↓
756 条新闻 + 关键词 + 事件 全部回滚丢失
         ↓
RunMetrics 记录 items_final=756（基于 INSERT RETURNING 的计数，在 rollback 之前）
```

### 3.2 为什么 RunMetrics 显示"成功"

`save_news()` 函数的返回值来自 `INSERT ... RETURNING` 的 `fetchall()` 计数（第 41-42 行）。这个值在 `session.commit()` 之前就确定了。即使 commit 实际执行了 rollback，返回值仍然是 756。

```python
# writer.py 原代码
result = await session.execute(stmt)
inserted_rows = result.fetchall()
saved = len(inserted_rows)  # ← 这里是 756，但 commit 后实际为 0
```

### 3.3 为什么事务会回滚

PostgreSQL 的事务语义：**一条语句失败 → 整个事务 aborted → 后续所有操作失败 → commit 变成 rollback**。

Python 的 `try/except` 只捕获了 Python 层面的异常，但 PostgreSQL 的事务状态仍然是 aborted。当 `session.commit()` 被调用时，asyncpg 检测到事务已 abort，执行 ROLLBACK 而非 COMMIT。

### 3.4 时间线

| 日期 | 事件 |
|------|------|
| 5月31日 | 最后一次成功入库（227 条） |
| 6月1日 | 开始出现 StatementTooComplexError |
| 6月1日-7日 | 每次运行都失败，数据全部丢失 |
| 6月7日 | 添加了入库后校验（发现了问题但未修复根因） |
| 6月8日 | 本次修复 |

---

## 4. 修复方案

### 4.1 实体同步分批查询

**文件**: `scraper/pipeline/entities.py`

**问题代码**：
```python
# 一次性查询所有实体，keys 可能有数千个
result = await session.execute(
    select(Entity).where(
        tuple_(Entity.normalized_name, Entity.entity_type).in_(keys)
    )
)
```

**修复代码**：
```python
# 分批查询，每批 100 个
batch_size = 100
for i in range(0, len(keys), batch_size):
    batch = keys[i:i + batch_size]
    result = await session.execute(
        select(Entity).where(
            tuple_(Entity.normalized_name, Entity.entity_type).in_(batch)
        )
    )
    for e in result.scalars():
        existing[(e.normalized_name, e.entity_type)] = e.id
```

### 4.2 两阶段架构重构

**文件**: `scraper/db/writer.py`

**原架构**（单函数 190 行，7+ 职责，一个事务）：
```
save_news() {
    关键词同步 → commit
    INSERT 新闻 → RETURNING
    关键词匹配
    实体提取
    事件检测
    关键词关联 INSERT
    实体同步 ← 失败点
    关系计算
    commit ← 实际 rollback
}
```

**新架构**（两阶段分离）：
```
Phase 1: save_news_core() {
    INSERT 新闻 → RETURNING
    commit ← 原子、可靠
    返回 (count, {link_hash: article_id})
}

Phase 2: enrich_news() {
    _enrich_keywords()   ← 独立事务，可失败
    _enrich_entities()   ← 独立事务，可失败
    _enrich_events()     ← 独立事务，可失败
    _enrich_relations()  ← 独立事务，可失败
}
```

**设计原则**：
1. 核心数据与富化解耦 — 新闻写入不依赖任何富化步骤
2. 每个富化步骤独立事务 — 实体同步失败不会回滚关键词
3. 返回值真实反映结果 — `save_news_core` 返回的 count = 实际入库数
4. 可重试 — Phase 2 失败后可以单独重跑富化

### 4.3 调用方适配

**文件**: `scraper/run_news.py`

```python
# 修改前
saved = await save_news(all_items)

# 修改后
saved, hash_to_id = await save_news_core(all_items)
if hash_to_id:
    enrich_stats = await enrich_news(hash_to_id, all_items)
```

---

## 5. 修改文件清单

| 文件 | 改动 |
|------|------|
| `scraper/pipeline/entities.py` | `sync_entities_to_db` 分批查询（每批 100） |
| `scraper/db/writer.py` | 拆分为 `save_news_core()` + `enrich_news()` + 4 个 `_enrich_*()` 子函数；保留 `save_news()` 兼容接口 |
| `scraper/db/__init__.py` | 导出 `save_news_core`, `enrich_news` |
| `scraper/run_news.py` | 调用方改为两阶段调用 |

---

## 6. 数据流总览

```
RSS 源 (config.yaml: 48 个源)
  │
  ▼
1. 抓取 (Fetcher.fetch)
   HTTP GET → RSS XML
   支持 ETag/304 缓存
  │
  ▼
2. 解析 (parse_feed)
   RSS XML → [FeedItem(link, title, summary, date)]
  │
  ▼
3. 去重
   link_hash ∈ existing_hashes? → 跳过
   title 相似? → 跳过
  │
  ▼
4. 正文提取 (fetch_html + extract_article)
   访问文章链接 → HTML → 提取正文
  │
  ▼
5. 分类过滤 (classify_hybrid)
   关键词匹配 + LLM 语义分类 → 不相关丢弃
  │
  ▼
6. 元数据提取
   article_type + regions
  │
  ▼
═══════════════════════════════════════
  Phase 1: save_news_core()
  INSERT ... ON CONFLICT DO NOTHING
  原子、幂立、可验证
═══════════════════════════════════════
  │
  ▼
═══════════════════════════════════════
  Phase 2: enrich_news()
  ┌──────────┐ ┌──────────┐
  │ 关键词    │ │ 实体      │
  │ 独立事务  │ │ 独立事务  │
  └──────────┘ └──────────┘
  ┌──────────┐ ┌──────────┐
  │ 事件      │ │ 关系      │
  │ 独立事务  │ │ 独立事务  │
  └──────────┘ └──────────┘
  任一失败 → 只 log，不影响新闻数据
═══════════════════════════════════════
```

---

## 7. 排查检查清单

遇到类似"日志显示成功但数据未入库"问题时：

### 第一步：检查数据校验日志

```bash
grep "数据校验失败" logs/scraper.log | tail -5
```

### 第二步：检查事务相关错误

```bash
grep -B5 "数据校验失败" logs/scraper.log | grep -E "ERROR|WARNING|StatementTooComplex|rollback"
```

### 第三步：检查数据库实际状态

```python
# 检查最后入库时间
SELECT MAX(created_at), COUNT(*) FROM news;

# 检查 RunMetrics 与实际数据的一致性
SELECT started_at, items_final FROM run_metrics ORDER BY started_at DESC LIMIT 5;
```

### 第四步：检查 PostgreSQL 配置

```sql
SHOW stack_depth;        -- 默认 2MB，复杂查询可能超限
SHOW max_stack_depth;
```

---

## 8. 经验总结

1. **INSERT RETURNING 的计数 ≠ 实际入库数** — 如果事务 rollback，RETURNING 的结果也丢失
2. **Python try/except 不能修复 PostgreSQL 事务状态** — 一条语句失败后事务 aborted，必须 rollback 才能继续
3. **tuple_.in_(keys) 的参数数量有隐性上限** — PostgreSQL 的 stack_depth 限制，NER 提取的实体可能有数千个
4. **单函数多职责是脆弱性的根源** — 富化失败不应能回滚核心数据
5. **两阶段分离是数据管道的健壮模式** — 核心写入与 best-effort 富化解耦
6. **入库后校验是必要的安全网** — 但不能替代根因修复

---

## 9. 相关文件

| 文件 | 用途 |
|------|------|
| `scraper/db/writer.py` | 数据入库逻辑（两阶段架构） |
| `scraper/db/__init__.py` | 数据库模块导出 |
| `scraper/pipeline/entities.py` | 实体提取与同步（分批查询） |
| `scraper/run_news.py` | RSS 抓取主流程 |
| `scripts/check_pipeline.py` | 数据管道健康检查 |
| `docs/2026-06-07-rss-troubleshooting.md` | 上一次 RSS 故障排查记录 |

---

## 10. 全项目 Session 管理修复（同日追加）

在修复 `save_news()` 后，对项目进行了全面扫描，发现多处相同的 session 管理问题。提交 `f691ffa`。

### 10.1 问题扫描结果

使用代码分析工具扫描 `app/`、`scraper/`、`deep_analyst/`、`common/` 四个目录，发现 **16 处** 问题代码：

| 风险 | 数量 | 问题类型 |
|------|------|----------|
| 高 | 5 | 事务/session 管理：异常后继续使用可能损坏的 session |
| 中 | 5 | N+1 查询：循环中逐条执行数据库查询 |
| 低 | 6 | 大型函数 + 代码重复 |

### 10.2 高风险修复

#### `scraper/db/writer.py` — `_enrich_events` / `_enrich_relations`

**问题**：循环中逐条处理文章，单个失败后 session 可能处于脏状态，后续文章继续使用同一 session。

**修复**：每个文章使用 `begin_nested()` savepoint 隔离。

```python
# 修复前
for link_hash, article_id in hash_to_id.items():
    try:
        await process_article_event(session, item)  # 失败后 session 脏
    except Exception as e:
        logger.warning(...)

# 修复后
for link_hash, article_id in hash_to_id.items():
    try:
        async with session.begin_nested():  # SAVEPOINT
            await process_article_event(session, item)
    except Exception as e:  # ROLLBACK TO SAVEPOINT
        logger.warning(...)  # session 仍然干净
```

#### `scraper/db/writer.py` — `batch_insert_entity_relations`

**问题**：某批次插入失败后，脏状态影响后续批次和最终 commit。

**修复**：每批使用 savepoint 隔离。

```python
# 修复前
for batch in batches:
    try:
        await session.execute(stmt)  # 失败后脏状态扩散
    except:
        pass  # 继续下一批，但 session 已坏

# 修复后
for batch in batches:
    try:
        async with session.begin_nested():
            await session.execute(stmt)
    except:
        pass  # savepoint 回滚，session 干净
```

#### `scraper/db/writer.py` — `process_article_event`

**问题**：内部 try/except 吞掉异常，`session.add()` 的脏状态不会回滚，调用方无法感知失败。

**修复**：移除内部 try/except，异常由调用方的 savepoint 处理。

```python
# 修复前
try:
    session.add(new_event)
    return {...}
except Exception as e:
    logger.error(...)  # session.add 的脏状态留在 session 中
    return None

# 修复后
session.add(new_event)
return {...}
# 异常自然传播到调用方的 begin_nested()，由 savepoint 回滚
```

#### `deep_analyst/pipeline.py` — `run_deep_analysis`

**问题**：多个事件共享同一 session，前一个事件失败后 session 状态不确定，后续事件继续使用。

**修复**：每个事件使用 savepoint，统一 commit。

```python
# 修复前
for event_data in events:
    result = await analyze_single_event(session, event_data, ai_client)
    if result.success:
        await session.commit()  # 每个事件单独 commit，失败后下一个继续用脏 session

# 修复后
for event_data in events:
    try:
        async with session.begin_nested():
            result = await analyze_single_event(session, event_data, ai_client)
    except Exception as e:
        ...  # savepoint 回滚，session 干净
await session.commit()  # 统一提交所有成功的分析
```

#### `deep_analyst/pipeline.py` — `analyze_single_event`

**问题**：4 个分析步骤（知识框架→因果链→历史类比→情景推演）共享同一 session，任一步骤部分写入失败会污染后续步骤。

**修复**：每个步骤使用独立 savepoint。

```python
# 修复后
try:
    async with session.begin_nested():
        knowledge = await analyze_event_knowledge(...)
        await _save_knowledge(session, ...)
        result.steps_completed.append("knowledge")
except Exception as e:
    result.steps_failed.append("knowledge")

try:
    async with session.begin_nested():
        causal = await analyze_causal_chain(...)
        await _save_causal_chain(session, ...)
        result.steps_completed.append("causal_chain")
except Exception as e:
    result.steps_failed.append("causal_chain")
# ... Step 3, Step 4 同理
```

### 10.3 中风险修复

#### N+1 查询 → 批量查询

**问题**：`_save_knowledge` 和 `trigger_knowledge_analysis` 中，对每个知识原子执行：
1. `SELECT` 检查原子是否存在
2. `INSERT` + `flush`（如果不存在）
3. `SELECT` 检查关联是否存在
4. `INSERT` 关联（如果不存在）

756 篇文章 × 每篇 N 个原子 = 数千次数据库查询。

**修复**：改为批量查询 + 批量插入。

```python
# 修复前：N+1
for atom_data in atoms_data:
    existing = await session.execute(select(...).where(title == atom_data["title"]))  # N 次 SELECT
    if not existing:
        session.add(atom)
        await session.flush()
    link_exists = await session.execute(select(...).where(atom_id == atom.id))  # N 次 SELECT

# 修复后：批量
atom_titles = [(a["title"], "zh") for a in atoms_data]
result = await session.execute(
    select(KnowledgeAtom).where(
        tuple_(KnowledgeAtom.title, KnowledgeAtom.lang).in_(atom_titles)  # 1 次 SELECT
    )
)
existing_atoms = {(a.title, a.lang): a for a in result.scalars()}

# 批量检查关联
result = await session.execute(
    select(EventKnowledgeAtom.atom_id).where(
        EventKnowledgeAtom.event_id == event_id,
        EventKnowledgeAtom.atom_id.in_(atom_ids),  # 1 次 SELECT
    )
)
existing_link_ids = {row[0] for row in result.fetchall()}
```

#### `trigger_analogy_analysis` — 循环中 AI 调用隔离

**问题**：循环中逐个候选事件调用 AI API，单个失败可能污染 session 中已写入的 EventRepresentation。

**修复**：每个候选事件使用 savepoint 隔离。

```python
# 修复后
for candidate in candidates:
    try:
        async with session.begin_nested():
            analogy_result = await analyze_analogy(source_data, target_data, ai_client)
            if analogy_result:
                session.add(HistoricalAnalogy(...))
    except Exception as e:
        logger.warning(f"类比分析失败 (candidate={candidate.event_id}): {e}")
```

### 10.4 修改文件清单

| 文件 | 改动 |
|------|------|
| `scraper/db/writer.py` | `_enrich_events` / `_enrich_relations` / `batch_insert_entity_relations` / `process_article_event` |
| `deep_analyst/pipeline.py` | `run_deep_analysis` / `analyze_single_event` / `_save_knowledge` |
| `deep_analyst/router.py` | `trigger_knowledge_analysis` / `trigger_analogy_analysis` |

### 10.5 统一修复模式

所有修复遵循同一模式：**savepoint 隔离**。

```python
# 原则：每个可能失败的独立操作用 savepoint 包裹
for item in items:
    try:
        async with session.begin_nested():  # SAVEPOINT
            await process(session, item)
    except Exception:  # ROLLBACK TO SAVEPOINT
        logger.warning(...)
        # session 仍然干净，下一个 item 正常处理

await session.commit()  # 统一提交所有成功的操作
```

**适用场景**：
- 循环中处理多个独立项目（文章、事件、候选类比）
- 多步骤流水线（知识框架→因果链→类比→推演）
- 分批插入（每批独立）

**不适用场景**：
- 操作之间有依赖关系（后一步依赖前一步的结果）
- 需要原子性的批量操作（要么全成功要么全失败）

### 10.6 测试验证

```
200 passed, 1 warning in 2.55s
```

所有现有测试通过，无回归。
