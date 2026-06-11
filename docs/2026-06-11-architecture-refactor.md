# 2026-06-11 架构重构：Alembic 迁移集成

## 会话概述

本次会话对蛰 (Zheye) 项目进行架构分析，识别改进方向，并完成 P1 阶段的 Alembic 迁移集成。

---

## 一、架构分析

### 1.1 现有架构评估

| 模块 | 状态 | 评价 |
|------|------|------|
| RSS 抓取管道 | 完整 | 两阶段架构（抓取 + 富化），智能调度 |
| 数据库设计 | 完整 | 18 张表，关系清晰 |
| AI 分析 | 完整 | 两层分析（基础 + 深度），版本管理 |
| Web 应用 | 完整 | FastAPI + HTMX，中英文支持 |
| 部署配置 | 缺失 | 无 Dockerfile，无 Alembic 迁移管理 |

### 1.2 识别的架构问题

#### 高优先级

| 问题 | 位置 | 影响 |
|------|------|------|
| 事件检测脆弱 | `events.py` 用 MD5(title[:30]) | 同一事件因标题微小变化而碎片化 |
| 无调度器集成 | `apscheduler` 在 requirements 中但未使用 | AI 分析只能手动触发 |
| 无并行 enrichment | Phase 2 四步串行执行 | 40+ 源处理耗时 10-20 分钟 |
| 批量处理过于保守 | `BATCH_SIZE=3`，30-60s 间隔 | 健康源也被拖慢 |

#### 中优先级

| 问题 | 位置 | 影响 |
|------|------|------|
| 翻译未集成 | `translate.py` 存在但未接入主流程 | 中文平台无英文标题翻译 |
| 无增量 TF-IDF | `tfidf_dedup.py` 每次重建矩阵 | O(n) 复杂度 |
| 全局可变状态 | 多处模块级单例 | 线程不安全，测试困难 |
| AI 客户端无 DI | `DeepSeekClient()` 直接实例化 | 资源浪费，难替换 |

#### 低优先级 / 安全

| 问题 | 位置 | 影响 |
|------|------|------|
| Admin 仅 Basic Auth | `auth.py` | 无 HTTPS 时凭据明文传输 |
| Deep Analyst 无限流 | `POST /api/deep-analyst/*/analyze` | 滥用可耗尽 AI 预算 |
| 无 Alembic 迁移 | 手动 `psql -f` | 无法跟踪/回滚迁移 |
| 无数据清理 | `RETENTION_DAYS=30` 配置但未实现 | 旧数据无限堆积 |

---

## 二、重构方案

### 2.1 三阶段渐进式重构

```
Phase 1（基础治理）    → 技术债务清理，不改功能
Phase 2（DI + 管线）   → 可测试性 + 性能优化
Phase 3（功能增强）    → 补齐缺失能力
```

### 2.2 Phase 1 详细方案

| 任务 | 耗时 | 收益 |
|------|------|------|
| Alembic 迁移集成 | 0.5 天 | 运维安全 |
| 清理死代码 | 0.5 天 | 可维护性 |
| Lifespan 统一管理 | 1 天 | 消除全局状态 |

### 2.3 Phase 2 详细方案

| 任务 | 耗时 | 收益 |
|------|------|------|
| DI 容器 | 2 天 | 可测试性 |
| Phase 2 并行化 | 1 天 | 性能 3-5x |
| 智能调度 | 1 天 | 吞吐提升 |

### 2.4 Phase 3 详细方案

| 任务 | 耗时 | 收益 |
|------|------|------|
| 事件检测升级 | 2 天 | 数据质量 |
| APScheduler 集成 | 1 天 | 自动化 |
| 翻译 + 清理 | 1 天 | 功能补全 |

---

## 三、已完成：Alembic 迁移集成

### 3.1 变更概述

将手动 SQL 迁移（`migrations/versions/*.sql`）迁移到 Alembic 管理，实现：
- 版本跟踪（`alembic_version` 表）
- 迁移历史记录
- 升级/回滚能力
- 与现有 SQLAlchemy 模型集成

### 3.2 新增文件

| 文件 | 用途 |
|------|------|
| `alembic.ini` | Alembic 配置，从 `DATABASE_URL` 环境变量读取连接 |
| `alembic/env.py` | 异步 PostgreSQL 支持，导入所有核心 models |
| `alembic/versions/000_legacy.py` | 基础 revision，代表 18 个 legacy SQL 迁移已应用 |
| `scripts/stamp_migrations.py` | 脚本：将数据库标记为 `000_legacy`（已应用） |

### 3.3 技术决策

#### 为什么使用 `000_legacy` 而不是 `base`？

Alembic 保留了 `base`、`head`、`heads` 等符号名称。如果 revision ID 为 `base`，会导致 `walk_revisions()` 方法在 `_topological_sort` 中出现断言错误。使用 `000_legacy` 避免了命名冲突。

#### 为什么 env.py 不导入 deep_analyst 模型？

`deep_analyst` 模块的导入链会触发 `yaml` 等依赖包的加载（`deep_analyst/utils.py` → `scraper/pipeline/classify.py` → `import yaml`）。在 Alembic 运行时这些依赖可能不可用，导致导入失败。核心 models 已足够覆盖主要表结构。

#### 为什么保留 legacy SQL 文件？

作为历史参考和备份。如果 Alembic 配置出现问题，仍可使用 `psql -f` 手动执行。

### 3.4 使用方法

```bash
# 1. 首次部署：创建表结构 + 标记版本
# 先用 legacy SQL 创建表
for f in migrations/versions/*.sql; do psql -f "$f"; done

# 然后标记 Alembic 版本
DATABASE_URL=postgresql+asyncpg://user:pass@host/db \
  python scripts/stamp_migrations.py

# 2. 后续变更：创建新 migration
alembic revision -m "描述变更内容"

# 3. 应用变更
alembic upgrade head

# 4. 回滚
alembic downgrade -1

# 5. 查看当前版本
alembic current
```

### 3.5 测试验证

| 测试项 | 结果 |
|--------|------|
| stamp 脚本执行 | ✅ 成功标记 `000_legacy` |
| alembic current | ✅ 显示 `000_legacy (head)` |
| 创建新 migration | ✅ 自动生成 revision 文件 |
| alembic upgrade | ✅ 执行 `ALTER TABLE` |
| alembic downgrade | ✅ 回滚 `DROP COLUMN` |
| 清理后状态 | ✅ 回到 `000_legacy (head)` |

### 3.6 已知问题

- `alembic/history` 和 `alembic/branches` 在 Alembic 1.13/1.18 存在 bug，用 `alembic heads` 代替
- `deep_analyst` 模型未导入 env.py，如需 autogenerate 需手动添加
- Post-write hook（ruff）已禁用，需手动安装 ruff 后启用

---

## 四、后续待实施任务

### 4.1 P1 剩余任务

- [ ] 清理死代码（`utils.py`、`translation_cache.py`）
- [ ] Lifespan 统一管理（消除全局状态）

### 4.2 P2 任务

- [ ] DI 容器（`fastapi.Depends()`）
- [ ] Phase 2 并行化（`asyncio.gather()`）
- [ ] 智能批量调度（按源健康度分层）

### 4.3 P3 任务

- [ ] 事件检测算法升级（语义相似度替代 MD5）
- [ ] APScheduler 集成
- [ ] 翻译集成 + 数据清理

---

## 五、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `alembic.ini` | 新增 | Alembic 配置文件 |
| `alembic/env.py` | 新增 | 异步 PostgreSQL 环境配置 |
| `alembic/script.py.mako` | 新增 | 迁移模板 |
| `alembic/versions/000_legacy.py` | 新增 | 基础 revision |
| `scripts/stamp_migrations.py` | 新增 | 版本标记脚本 |
| `requirements.txt` | 已含 | `alembic` 已在依赖中 |

---

## 六、测试结果

```
✅ stamp 脚本         → alembic_version = 000_legacy
✅ alembic current    → 000_legacy (head)
✅ 创建新 migration   → 自动生成 revision 文件
✅ alembic upgrade    → ALTER TABLE news ADD COLUMN test_column
✅ alembic downgrade  → ALTER TABLE news DROP COLUMN test_column
✅ 清理后             → 回到 000_legacy (head)
```
