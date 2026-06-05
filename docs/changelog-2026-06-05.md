# 2026-06-05 代码质量与性能优化会话记录

## 会话概述

本次会话主要对蛰 (Zheye) 项目进行全面的代码质量检查和性能优化，包括修复代码缺陷、消除重复代码、异步化改造、数据库优化等。

---

## 一、项目运行情况检查

### 1.1 Web 服务状态
- **进程**: uvicorn 正在运行 (PID 1899263)
- **端口**: 监听 `0.0.0.0:8000`
- **状态**: HTTP 200，API 正常返回数据
- **Systemd**: 服务状态 `active`

### 1.2 Scraper 服务问题
**问题**: `scraper/run_news.py` 缺失导入导致 `NameError`

**修复**: 添加所有缺失的导入语句
```python
from scraper.sources import Fetcher, parse_feed, extract_article_from_html, extract_date_from_html
from scraper.pipeline import get_link_hash, is_duplicate
from scraper.pipeline.classify import classify_hybrid, detect_article_type
from scraper.pipeline.regions import extract_regions
from scraper.pipeline.dedup import add_to_dedup_cache
from scraper.pipeline.scheduler import filter_and_sort_sources, get_health_summary
from scraper.db import update_source_health, save_news, get_existing_hashes, get_existing_titles
from scraper.db.writer import get_source_conditional_headers
from scraper.sources.api_fetcher import MarketDataFetcher
from scraper.monitor import reset_monitor, get_monitor
from models.base import async_session
from models.run_metrics import RunMetrics
from models.market_data import MarketData
```

---

## 二、P0/P1 问题修复

### 2.1 P0 问题

| 问题 | 位置 | 修复方案 |
|------|------|---------|
| `Float` 未导入导致运行时崩溃 | `deep_analyst/knowledge.py:884` | 添加 `Float` 到 sqlalchemy 导入 |

### 2.2 P1 问题

| 问题 | 修复方案 |
|------|---------|
| 异步化 AI 调用 (`time.sleep` 阻塞) | 将 `time.sleep()` 替换为 `asyncio.sleep()` |
| `utils.py` 重复代码 (198行 x 2) | 提取到 `common/utils.py` |
| `DeepSeekClient` 重复代码 (~400行 x 2) | 提取基类到 `common/ai_client.py` |
| `_generate_mermaid` 重复代码 | 提取到 `common/mermaid.py` |
| fire-and-forget 异步任务无错误处理 | 添加 `done_callback` 异常处理 |

### 2.3 新增共享模块

```
common/
├── __init__.py
├── ai_client.py      # BaseDeepSeekClient 基类
├── mermaid.py        # Mermaid 图表生成
└── utils.py          # 共享工具函数
```

---

## 三、P2 问题修复

| 问题 | 修复方案 |
|------|---------|
| 缓存 per-item TTL 不生效 | 重写缓存模块，实现 `PerItemTTLCache` 类 |
| `models/__init__.py` 未导出全部模型 | 添加 `AnalysisVersion` 和 `FailedAnalysisTask` 导出 |
| 硬编码分页大小 | 将 `page_size = 20` 改为 `settings.DEFAULT_PAGE_SIZE` |

### 3.1 缓存模块改进

新的 `PerItemTTLCache` 类支持：
- 每个缓存项独立的 TTL
- 惰性清理过期项
- LRU 淘汰策略
- 详细的统计信息

---

## 四、异步化 AI 调用

### 4.1 问题
```python
# 之前：阻塞事件循环
time.sleep(wait_time)
```

### 4.2 修复
```python
# 之后：非阻塞
await asyncio.sleep(wait_time)
```

### 4.3 修改文件
- `scraper/pipeline/ai_analysis.py`
- `deep_analyst/ai_analysis.py`
- `scraper/pipeline/classify.py`
- `scraper/pipeline/llm_classifier.py`
- `scraper/pipeline/utils.py`
- `deep_analyst/utils.py`
- `scraper/run_news.py`

### 4.4 性能提升
多个 AI 调用可并发执行，不再串行等待。

---

## 五、移除每日报告功能

根据需求，移除每日报告功能，仅保留每周和每月报告。

### 5.1 移除内容
- API 端点 `/api/analysis/daily/{date}` 和 `/api/analysis/latest`
- `DeepSeekClient.generate_daily_report` 方法
- `DailyReport` 数据类
- 相关测试

### 5.2 保留内容
- 每周报告 (`/api/analysis/weekly/{date}`)
- 每月报告 (`/api/analysis/monthly/{date}`)
- 文章分析功能

---

## 六、定时任务脚本

### 6.1 新增脚本

| 脚本 | 功能 | 建议调度 |
|------|------|---------|
| `scripts/cleanup_old_data.py` | 清理旧新闻、运行指标、失败任务 | 每天凌晨2点 |
| `scripts/run_quality_decay.py` | 知识原子质量衰减 | 每天凌晨3点 |
| `scripts/retry_failed_tasks.py` | 失败任务自动重试 | 每小时 |

### 6.2 Crontab 配置示例

```bash
# 每天凌晨2点清理旧数据
0 2 * * * cd /opt/zheye && python scripts/cleanup_old_data.py

# 每天凌晨3点执行质量衰减
0 3 * * * cd /opt/zheye && python scripts/run_quality_decay.py

# 每小时重试失败任务
0 * * * * cd /opt/zheye && python scripts/retry_failed_tasks.py
```

---

## 七、数据库性能优化

### 7.1 索引优化

| 优先级 | 优化内容 |
|--------|----------|
| **P0** | 为 `failed_analysis_tasks` 添加 3 个索引 |
| **P1** | 为 `news.regions` 添加 GIN 索引 |
| **P2** | 删除 7 个冗余索引 |

### 7.2 查询优化

| 问题 | 修复方案 |
|------|---------|
| `DATE()` 函数阻止索引 | 改用 `date::date` 或范围查询 |
| `retry_all_failed_tasks` N+1 | 改为批量 UPDATE |

### 7.3 连接池优化

| 参数 | 原值 | 新值 |
|------|------|------|
| `pool_size` | 5 | 10 |
| `max_overflow` | 10 | 15 |
| `pool_recycle` | 3600 | 1800 |
| `pool_timeout` | 默认30 | 10 |
| `pool_use_lifo` | False | True |

### 7.4 数据类型优化
- `news.lang` 添加 `nullable=False`
- `news.ai_importance` 添加 `default=0.0`
- `failed_task.status` 添加 `nullable=False`

---

## 八、代码清理

### 8.1 清理未使用的导入

| 文件 | 移除的导入 |
|------|-----------|
| `app/routes/api_events.py` | `datetime` |
| `app/routes/api_analysis.py` | `datetime` |
| `app/routes/admin.py` | `json` |
| `scraper/run_news.py` | `os` |

### 8.2 替换已弃用的 API

将所有 `datetime.utcnow()` 替换为 `datetime.now(timezone.utc)`：
- `models/failed_task.py`
- `scraper/pipeline/retry_manager.py`
- `scraper/pipeline/ai_analysis.py`
- `deep_analyst/pipeline.py`
- `deep_analyst/knowledge.py`

### 8.3 修复重复创建 Limiter 实例

`app/routes/api_common.py` 现在从 `app.main` 导入 `limiter` 实例，确保整个应用使用同一个速率限制器。

---

## 九、预期优化效果

| 优化项 | 预期效果 |
|--------|----------|
| 异步化 AI 调用 | 并发性能提升 5-10x |
| 添加数据库索引 | 查询速度提升 10-100x |
| 移除 DATE() 包装 | 查询速度提升 5-50x |
| 批量更新替代 N+1 | 响应时间减少 90%+ |
| 删除冗余索引 | 写入性能提升 5-15% |
| 连接池优化 | 减少连接等待时间 |

---

## 十、提交记录

| 提交哈希 | 说明 |
|----------|------|
| `15c5f5a` | fix: 修复多个代码质量问题 |
| `797f8a2` | fix: 修复 deep_analyst/knowledge.py 中 Float 未导入的问题 |
| `8173a3e` | refactor: 异步化 AI 调用，提升并发性能 |
| `282a6ed` | refactor: 消除重复代码，提取共享模块 |
| `2a8c286` | fix: 修复 P2 问题 |
| `fe09d71` | feat: 添加定时任务脚本，移除每日报告功能 |
| `4644d9a` | perf: 数据库性能优化 |

---

## 十一、测试验证

所有修改均通过测试验证：
- **测试数量**: 200 个
- **通过率**: 100%
- **警告**: 1 个（Pydantic 配置弃用警告）

---

## 十二、后续优化建议

1. **全文搜索优化**: 添加 `tsvector` 生成列 + GIN 索引
2. **物化视图**: 对高频聚合查询创建物化视图
3. **数据保留策略**: 配置定时清理过期数据
4. **Docker 支持**: 创建 Dockerfile 简化部署
