# RSS 数据管道故障排查记录

**日期**: 2026-06-07  
**问题**: RSS 抓取数据未显示到前端  
**严重程度**: 高（数据完全缺失约一周）

---

## 1. 问题描述

用户反馈前端未显示最近几天的 RSS 新闻数据。日志显示每次抓取运行成功（`Saved 712 new items to database`），但数据库中无对应数据。

---

## 2. 诊断过程

### 2.1 数据库状态检查

```sql
-- 检查数据分布
SELECT DATE(created_at) as date, COUNT(*) as count
FROM news GROUP BY DATE(created_at) ORDER BY date;

-- 结果：只有 2026-05-31 的 227 条数据，6月1日-6日完全缺失
```

**关键发现**：
- 最新 `created_at` 为 `2026-05-31 10:38:02`
- 最大 `id` 为 25658，但只有 227 条数据
- ID 间隙 25428，说明大量数据被插入后删除

### 2.2 ID 间隙分析

```sql
SELECT MAX(id), MIN(id), COUNT(*) FROM news;
-- 结果：max_id=25658, min_id=1, count=227
-- 间隙 = 25658 - 227 = 25431
```

**结论**：数据被插入（占用 ID）后又被删除。

### 2.3 源健康状态检查

```python
# 查询连续失败的源
SELECT source_name, consecutive_failures, last_error
FROM source_health
WHERE consecutive_failures > 0
ORDER BY consecutive_failures DESC;
```

**失败源分类**：

| 类型 | 源 | 错误 |
|------|-----|------|
| 404 URL 失效 | ECB Blog, Gulf News, World Bank Blogs, Nikkei Asia, VoxEU, Business Day | RSS 地址变更 |
| 403 访问拒绝 | IMF News, IMF Blog, Foreign Affairs, Arab News | 反爬虫/地理限制 |
| 429 Rate Limit | Yahoo Finance | IP 被限制 |
| 401 付费墙 | WSJ, MarketWatch, Seeking Alpha | 文章页面需付费 |

### 2.4 日志分析

```bash
# 统计 429 错误分布
grep "429" logs/scraper.log | grep -oP "for https?://[^/]+" | sort | uniq -c | sort -rn

# 结果：
# 41 finance.yahoo.com
#  5 bloomberg.com
#  4 dealbreaker.com
```

---

## 3. 根因分析

### 3.1 RSS 源失效原因

| 原因 | 比例 | 说明 |
|------|------|------|
| URL 失效 (404) | 45% | 网站改版、RSS 路径变更 |
| 访问拒绝 (403) | 30% | 反爬虫机制、地理限制 |
| Rate Limiting (429) | 15% | 频繁访问触发 IP 限制 |
| 付费墙 (401) | 10% | 文章内容需订阅 |

### 3.2 数据丢失原因

**未完全确认**，但以下因素相关：
1. `cleanup_old_data.py` 脚本存在但未在 crontab 中
2. 数据库无触发器或规则
3. 可能存在手动执行或未记录的定时任务

---

## 4. 解决方案

### 4.1 RSS 源修复

**config.yaml 修改**：

```yaml
# 禁用失效源（11个）
- name: ECB Blog
  enabled: false

# 付费墙源跳过 HTML 抓取
- name: WSJ
  skip_html_fetch: true
```

**最终配置**：
- 启用源：37 个
- 禁用源：11 个
- 跳过 HTML 抓取：4 个（WSJ, MarketWatch, Seeking Alpha, Yahoo Finance）

### 4.2 降低抓取频率

**run_news.py 修改**：

```python
# 修改前
BATCH_SIZE = 4
BATCH_DELAY_MIN = 20.0
BATCH_DELAY_MAX = 45.0
ARTICLE_DELAY_MIN = 2.0
ARTICLE_DELAY_MAX = 5.0

# 修改后
BATCH_SIZE = 3
BATCH_DELAY_MIN = 30.0
BATCH_DELAY_MAX = 60.0
ARTICLE_DELAY_MIN = 3.0
ARTICLE_DELAY_MAX = 7.0
```

**fetcher.py 修改**：

```python
# 修改前
DOMAIN_MIN_DELAY = 6.0
DOMAIN_MAX_DELAY = 15.0

# 修改后
DOMAIN_MIN_DELAY = 10.0
DOMAIN_MAX_DELAY = 20.0
```

### 4.3 数据保护措施

**1. writer.py - 入库后校验**

```python
# 提交后校验：确认数据实际写入数据库
verify_result = await session.execute(
    select(func.count(News.id)).where(News.link_hash.in_(list(hash_to_id.keys())))
)
verified_count = verify_result.scalar()
if verified_count != saved:
    logger.error(f"数据校验失败: 预期 {saved} 条, 实际入库 {verified_count} 条")
```

**2. cleanup_old_data.py - 安全防护**

```python
# RETENTION_DAYS=0 时跳过清理
if retention_days == 0:
    logger.info("RETENTION_DAYS=0, 数据永不删除策略已启用，跳过清理")
    return

# 必须显式确认才能删除
if not args.confirm and not args.dry_run:
    logger.error("安全检查: 必须指定 --confirm 或 --dry-run 才能执行")
    return
```

**3. .env 配置**

```bash
RETENTION_DAYS=0  # 0 = 永不删除，数据永久保留用于分析
```

---

## 5. 新增工具

### 5.1 数据管道健康检查脚本

**文件**: `scripts/check_pipeline.py`

**功能**：
- 最近入库检查
- 运行指标一致性校验
- 数据时间连续性检查
- 源健康状态检查
- ID 连续性检查（检测数据删除）

**使用方法**：

```bash
# 检查最近 2 小时
python scripts/check_pipeline.py

# 检查最近 24 小时
python scripts/check_pipeline.py --hours 24
```

**输出示例**：

```
==================================================
数据管道健康检查
==================================================

--- 最近入库检查 ---
[OK] 最近2小时入库数据: 150 条

--- 运行指标一致性 ---
[FAIL] 运行 2026-06-07 08:00: 指标显示保存 712 条, 实际入库 0 条

--- ID连续性 ---
[WARN] ID间隙异常: max_id=25759, count=331, gap=25428
  可能原因: 数据被删除或大量插入后回滚

检查结果汇总:
  [PASS] 最近入库检查
  [FAIL] 运行指标一致性
  [FAIL] ID连续性

结论: 数据管道存在问题，请检查上方详情
```

---

## 6. 排查检查清单

遇到类似问题时，按以下顺序排查：

### 第一步：确认数据是否入库

```sql
-- 检查最近数据
SELECT DATE(created_at), COUNT(*)
FROM news
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at);

-- 检查 ID 间隙
SELECT MAX(id) - COUNT(*) as gap FROM news;
```

### 第二步：检查日志

```bash
# 检查保存成功日志
grep "批量插入完成" logs/scraper.log | tail -5

# 检查数据校验日志（新版本）
grep "数据校验" logs/scraper.log

# 检查错误
grep -E "ERROR|失败|rollback" logs/scraper.log | grep -v "trafilatura"
```

### 第三步：检查源健康

```bash
# 运行健康检查
python scripts/check_pipeline.py

# 或直接查询数据库
python -c "
import asyncio
from models.base import async_session
from models.source_health import SourceHealth
from sqlalchemy import select

async def check():
    async with async_session() as session:
        result = await session.execute(
            select(SourceHealth).where(SourceHealth.consecutive_failures > 0)
        )
        for h in result.scalars():
            print(f'{h.source_name}: {h.consecutive_failures} failures')

asyncio.run(check())
"
```

### 第四步：检查是否有数据删除

```sql
-- 检查触发器
SELECT * FROM information_schema.triggers
WHERE event_object_table = 'news';

-- 检查规则
SELECT * FROM pg_rules WHERE tablename = 'news';
```

### 第五步：检查定时任务

```bash
# 用户 crontab
crontab -l

# 系统定时任务
ls /etc/cron.d/ /etc/cron.daily/

# systemd 定时器
systemctl list-timers
```

---

## 7. 预防措施

### 7.1 定期监控

建议 crontab 添加：

```bash
# 每天早上 8 点检查数据管道
0 8 * * * cd /opt/zheye && /opt/zheye/venv/bin/python scripts/check_pipeline.py --hours 24 >> /opt/zheye/logs/pipeline-check.log 2>&1
```

### 7.2 数据保护原则

1. **永不自动删除数据**：`RETENTION_DAYS=0`
2. **入库后校验**：提交事务后验证数据实际写入
3. **操作需确认**：清理脚本必须 `--confirm` 参数
4. **保留操作日志**：所有删除操作记录到日志

### 7.3 RSS 源维护

定期检查失效源：

```bash
# 测试 RSS 源可访问性
curl -s -o /dev/null -w "%{http_code}" "https://example.com/rss"
```

---

## 8. 相关文件

| 文件 | 用途 |
|------|------|
| `scraper/db/writer.py` | 数据入库逻辑，含入库后校验 |
| `scraper/run_news.py` | RSS 抓取主流程 |
| `scraper/sources/config.yaml` | RSS 源配置 |
| `scraper/sources/fetcher.py` | HTTP 请求逻辑 |
| `scripts/cleanup_old_data.py` | 数据清理脚本（含安全防护） |
| `scripts/check_pipeline.py` | 数据管道健康检查 |
| `.env` | 环境配置（RETENTION_DAYS=0） |

---

## 9. 经验总结

1. **日志显示成功 ≠ 数据入库**：需要入库后校验
2. **ID 间隙是重要线索**：大量间隙说明数据被删除
3. **429 错误会扩散**：一个源被限制可能影响其他源
4. **清理脚本需要安全防护**：默认不删除，删除需确认
5. **定期健康检查**：主动发现问题比被动响应好
