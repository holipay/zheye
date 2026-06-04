# 代码改进修复记录

**日期**: 2026-06-04  
**分支**: main  
**提交**: 多次提交

---

## 一、安全修复 (高优先级)

### S1 - deep_analyst/ai_analysis.py 中 metrics 未定义
- **问题**: `_call_api` 方法中引用了未定义的 `metrics` 变量，导致运行时 `NameError`
- **修复**: 添加 `from app.ai_metrics import get_ai_metrics` 导入
- **文件**: `deep_analyst/ai_analysis.py`

### S2 - deep_analyst/ai_analysis.py 中 Schema 类未导入
- **问题**: `analyze_article`、`generate_daily_report`、`analyze_keyword_trend` 方法引用了未导入的 Schema 类
- **修复**: 添加 `from models.schemas import ArticleAnalysisSchema, DailyReportSchema, TrendSchema` 导入
- **文件**: `deep_analyst/ai_analysis.py`

### S3 - 分析 API 缺少认证保护
- **问题**: `retry_failed_task`、`retry_all_failed_tasks`、`delete_failed_task`、`cleanup_failed_tasks` 端点缺少认证
- **修复**: 为所有 POST/DELETE 端点添加 `Depends(verify_admin_credentials)`
- **文件**: `app/routes/api_analysis.py`

### S4 - 分析 API 缺少速率限制
- **问题**: 分析 API 的 GET 端点没有速率限制，容易被恶意请求
- **修复**: 为所有 GET 端点添加 `@limiter.limit(settings.RATE_LIMIT_API)`
- **文件**: `app/routes/api_analysis.py`

### S5 - Admin YAML 写入缺少输入验证
- **问题**: `update_source` 端点直接使用 `request.json()`，没有验证输入数据
- **修复**: 添加 `SourceUpdateRequest` Pydantic 模型进行输入验证
- **文件**: `app/routes/admin.py`

### S6 - ADMIN_PASSWORD 空值降级行为
- **问题**: 未配置 `ADMIN_PASSWORD` 时，管理后台行为不明确
- **修复**: 在应用启动时添加配置检查和警告
- **文件**: `app/main.py`

---

## 二、错误修复 (高优先级)

### E1 - 数据库会话缺少事务管理
- **问题**: `get_session` 生成器没有自动 commit/rollback
- **修复**: 添加 try/except 块，异常时自动 rollback
- **文件**: `models/base.py`

### E2 - page 参数无最小值限制
- **问题**: `page` 参数可以传入负数或零
- **修复**: 添加 `Query(default=1, ge=1)` 验证
- **文件**: `app/routes/api_news.py`

### E3 - page_size 参数无上限限制
- **问题**: `page_size` 参数可以传入极大值
- **修复**: 添加 `Query(default=20, ge=1, le=100)` 验证
- **文件**: `app/routes/api_news.py`

### E5 - 日志级别配置不统一
- **问题**: `run_news.py` 和 `main.py` 使用不同的日志配置
- **修复**: 统一使用 `settings.LOG_LEVEL` 配置日志级别
- **文件**: `app/main.py`, `scraper/run_news.py`

---

## 三、性能优化 (高优先级)

### P1 - get_existing_hashes 加载全量数据到内存
- **问题**: `get_existing_hashes` 加载 10000 条 hash 到内存
- **修复**: 只加载最近 7 天的数据，使用 `created_at` 索引过滤
- **文件**: `scraper/db/writer.py`

### P2 - 标题去重使用 O(n*m) 暴力比较
- **问题**: 每次调用 `is_duplicate` 都会遍历所有标题
- **修复**: 使用全局 TFIDFDeduplicator 实例，避免重复 fit
- **文件**: `scraper/pipeline/dedup.py`

---

## 四、架构改进

### C4 - charts.py 数据库会话管理不一致
- **问题**: `charts.py` 使用 `async with async_session()` 而非 `Depends(get_session)`
- **修复**: 统一使用 `Depends(get_session)` 依赖注入模式
- **文件**: `app/routes/charts.py`

### C5 - _get_event_and_articles 重复定义
- **问题**: `api_common.py` 和 `deep_analyst/router.py` 有相同的函数定义
- **修复**: `deep_analyst/router.py` 复用 `api_common._get_event_and_articles`
- **文件**: `deep_analyst/router.py`

### C2 - _record_failed_task 异步处理复杂
- **问题**: 异步事件循环处理逻辑复杂，可能导致任务丢失
- **修复**: 简化为 `asyncio.get_running_loop().create_task()` 模式
- **文件**: `scraper/pipeline/ai_analysis.py`

---

## 五、配置管理

### F2 - requirements 未锁定版本
- **问题**: `requirements.txt` 未指定版本号
- **修复**: 生成 `requirements.lock` 锁定所有依赖版本
- **文件**: `requirements.lock` (新增)

### F3 - Settings 未使用 Pydantic BaseSettings
- **问题**: `Settings` 类手动读取环境变量，缺少类型验证
- **修复**: 迁移到 `pydantic_settings.BaseSettings`
- **文件**: `app/config.py`

### F4 - 支持语言集合重复定义
- **问题**: `SUPPORTED_LANGUAGES` 和 `DEFAULT_LANGUAGE` 在多处定义
- **修复**: `i18n.py` 从 `config.py` 导入
- **文件**: `app/i18n.py`

---

## 六、国际化

### C6 - API 错误消息硬编码中文
- **问题**: 错误消息使用硬编码中文，不利于国际化
- **修复**: 新增 `app/errors.py` 集中管理错误消息常量（中英文双语）
- **文件**: `app/errors.py` (新增), `app/auth.py`, `app/csrf.py`, `app/routes/admin.py`, `app/routes/api_analysis.py`, `app/routes/api_common.py`, `app/routes/api_events.py`, `deep_analyst/router.py`

---

## 七、清理

### A3 - Redis Streams 死代码
- **问题**: `scraper/queue/` 目录下的 Redis Streams 代码未被使用
- **修复**: 删除 `scraper/queue/` 目录和 `config.py` 中的 Redis 配置
- **文件**: `scraper/queue/` (删除), `app/config.py`

---

## 八、新增功能

### 历史事件基础数据
- **问题**: 历史类比功能缺少基础数据
- **修复**: 新增 `018_seed_historical_events.sql` 插入 20 个历史事件
- **文件**: `migrations/versions/018_seed_historical_events.sql`

---

## 未修复的问题

以下问题由于需要较大改动或保持模块独立性，暂未修复：

| 问题 | 原因 |
|------|------|
| C1 - DeepSeekClient 代码重复 | 用户决定保持 `deep_analyst` 独立 |
| C3 - sys.path.insert hack | 需要配置 pyproject.toml，影响较大 |
| C7 - utils 函数重复 | 用户决定保持 `deep_analyst` 独立 |
| P3 - 同步 AI 客户端阻塞事件循环 | 需要改用 AsyncOpenAI，影响较大 |
| P4 - TF-IDF 向量器重复 fit | 用户决定保持 `deep_analyst` 独立 |
| T1-T3 - 测试覆盖不足 | 需要较大工作量 |
| D1-D3 - 文档缺失 | 需要较大工作量 |

---

## 修复统计

- **修复问题数**: 22 个
- **修改文件数**: 20+ 个
- **新增文件数**: 3 个 (`app/errors.py`, `requirements.lock`, `018_seed_historical_events.sql`)
- **删除文件数**: 4 个 (`scraper/queue/` 目录)
