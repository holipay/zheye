# 2026-06-11 架构分析与 Alembic 迁移集成

## 会话概述

对蛰 (Zheye) 项目进行全面架构分析，制定三阶段重构方案，并完成 P1 阶段的 Alembic 迁移集成。

---

## 一、架构分析

### 1.1 项目现状

- **数据源**: 44+ RSS/API 源
- **数据库**: PostgreSQL，18 张表
- **AI 分析**: DeepSeek API，两层分析（基础 + 深度）
- **Web 应用**: FastAPI + HTMX，中英文支持
- **迁移管理**: 手动 `psql -f` 执行 18 个 SQL 文件

### 1.2 识别的关键问题

| 优先级 | 问题 | 影响 |
|--------|------|------|
| P0 | 无 Alembic 迁移管理 | 无法跟踪/回滚迁移 |
| P0 | 事件检测脆弱 (MD5 hash) | 同一事件碎片化 |
| P1 | 无调度器集成 | AI 分析只能手动触发 |
| P1 | Phase 2 串行执行 | 处理耗时 10-20 分钟 |
| P2 | 全局可变状态 | 线程不安全，测试困难 |
| P2 | AI 客户端无 DI | 资源浪费，难替换 |

---

## 二、重构方案

### 2.1 三阶段渐进式重构

```
Phase 1（基础治理，1-2 天）
├── Alembic 迁移集成 ✅ 已完成
├── 清理死代码
└── Lifespan 统一管理

Phase 2（DI + 管线，3-5 天）
├── DI 容器 (fastapi.Depends)
├── Phase 2 并行化 (asyncio.gather)
└── 智能批量调度

Phase 3（功能增强，5-7 天）
├── 事件检测算法升级
├── APScheduler 集成
└── 翻译 + 数据清理
```

---

## 三、已完成：Alembic 迁移集成

### 3.1 新增文件

| 文件 | 说明 |
|------|------|
| `alembic.ini` | Alembic 配置 |
| `alembic/env.py` | 异步 PostgreSQL 环境 |
| `alembic/versions/000_legacy.py` | 基础 revision |
| `scripts/stamp_migrations.py` | 版本标记脚本 |

### 3.2 技术决策

- 使用 `000_legacy` 而非 `base` 作为 revision ID，避免 Alembic 符号名称冲突
- env.py 仅导入核心 models，避免 deep_analyst 依赖链问题
- 保留 legacy SQL 文件作为历史参考

### 3.3 验证结果

```
✅ stamp 脚本         → alembic_version = 000_legacy
✅ alembic current    → 000_legacy (head)
✅ 创建新 migration   → 自动生成 revision 文件
✅ alembic upgrade    → ALTER TABLE 执行成功
✅ alembic downgrade  → 回滚成功
```

---

## 四、更新的文档

| 文件 | 变更 |
|------|------|
| `docs/DESIGN.md` | 更新目录结构、添加 Alembic 使用说明 |
| `docs/2026-06-11-architecture-refactor.md` | 完整架构分析和重构方案 |

---

## 五、Phase 1 完成情况

### ✅ Alembic 迁移集成
- 新增 `alembic.ini`, `alembic/env.py`, `alembic/versions/000_legacy.py`
- 新增 `scripts/stamp_migrations.py`

### ✅ 清理死代码
- 移除 `analyze_keyword_trend` 死方法 (`scraper/pipeline/ai_analysis.py`)
- 清理 `TrendSchema` 未使用导入
- 简化 `scraper/pipeline/utils.py`（移除 4 个未使用 re-export）
- 重构 `deep_analyst/utils.py` 直接导入 `common.utils`（消除双层间接引用）

### ✅ Lifespan 统一管理
- 新增 `app/lifespan.py`，统一管理应用生命周期
- 启动时：初始化翻译 HTTP 客户端
- 关闭时：清理 HTTP 客户端、spaCy 模型、数据库引擎
- 更新 `app/main.py` 使用 `lifespan` 参数

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/lifespan.py` | 新增 | 应用生命周期管理 |
| `app/main.py` | 修改 | 添加 lifespan 参数 |
| `scraper/pipeline/ai_analysis.py` | 修改 | 移除死方法和未使用导入 |
| `scraper/pipeline/utils.py` | 修改 | 简化 re-export |
| `deep_analyst/utils.py` | 修改 | 直接导入 common.utils |

---

## 七、Phase 2 完成情况

### ✅ DI 容器
- 新增 `app/deps.py` 统一管理 AI 客户端依赖
- `deep_analyst/router.py` 4 个 POST 路由改用 `Depends(get_ai_client_dependency)`
- `deep_analyst/pipeline.py` 支持可选 `ai_client` 参数
- `llm_classifier.py` 使用共享单例

### ✅ Phase 2 并行化
- `scraper/db/writer.py`: `enrich_news` 使用 `asyncio.gather` 并行执行 4 个富化步骤

### ✅ 智能调度
- 按健康度分层：健康源并发 10，不健康源并发 3
- 健康源批次延迟 2s，不健康源 15s

---

## 八、Phase 3 完成情况

### ✅ 事件检测升级
- 3级匹配：精确匹配 → 关键实体匹配 → 语义相似度
- 实体归一化：25bp = 25 basis points = 0.25%

### ✅ APScheduler 集成
- 每天 0:00 和 12:00 自动抓取新闻
- 每天凌晨 2:00 执行 AI 分析
- 每天凌晨 3:00 清理旧数据

### ✅ 翻译集成
- 英文标题自动翻译为中文（MyMemory API）

---

## 九、文件变更汇总

### 新增文件
| 文件 | 说明 |
|------|------|
| `alembic.ini` | Alembic 配置 |
| `alembic/env.py` | 异步 PostgreSQL 环境 |
| `alembic/versions/000_legacy.py` | 基础 revision |
| `app/lifespan.py` | 应用生命周期管理 |
| `app/deps.py` | FastAPI 依赖注入 |
| `scripts/stamp_migrations.py` | 版本标记脚本 |
| `docs/2026-06-11-architecture-refactor.md` | 架构分析文档 |
| `docs/changelog-2026-06-11.md` | 会话记录 |

### 修改文件
| 文件 | 变更 |
|------|------|
| `app/main.py` | 添加 lifespan 参数 |
| `deep_analyst/router.py` | 4 个路由改用 Depends |
| `deep_analyst/pipeline.py` | 支持可选 ai_client 参数 |
| `deep_analyst/utils.py` | 直接导入 common.utils |
| `scraper/pipeline/ai_analysis.py` | 移除死方法 |
| `scraper/pipeline/utils.py` | 简化 re-export |
| `scraper/pipeline/events.py` | 3级匹配 + 实体归一化 |
| `scraper/pipeline/llm_classifier.py` | 使用共享单例 |
| `scraper/pipeline/scheduler.py` | 分层调度 |
| `scraper/db/writer.py` | 并行化富化步骤 |
| `scraper/run_news.py` | 分层调度 + 翻译集成 |
| `docs/DESIGN.md` | 更新目录结构和部署步骤 |

---

## 十、提交记录

| 提交哈希 | 说明 |
|----------|------|
| `7cdec99` | refactor: Phase 1（Alembic + 死代码 + Lifespan） |
| `cc81314` | refactor: Phase 2（DI + 并行化 + 智能调度） |
| `5cc7a08` | feat: Phase 3（事件检测 + APScheduler + 翻译） |
