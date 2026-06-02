# 配置指南

## 快速开始

### 1. 创建配置文件

```bash
# 方法一：使用配置向导
python scripts/setup_config.py

# 方法二：手动创建
cp .env.example .env
# 编辑 .env 文件
```

### 2. 必需配置

| 配置项 | 说明 | 是否必需 |
|--------|------|----------|
| `DATABASE_URL` | PostgreSQL 数据库连接 | ✅ 必需 |

### 3. 可选配置

#### AI 分析功能

| 配置项 | 说明 | 获取方式 |
|--------|------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | [注册](https://platform.deepseek.com/) |

#### 市场数据 API

| 配置项 | 说明 | 免费配额 | 获取方式 |
|--------|------|----------|----------|
| `EXCHANGE_RATE_API_KEY` | 汇率数据 | 1500 请求/月 | [注册](https://www.exchangerate-api.com/) |
| `ALPHA_VANTAGE_API_KEY` | 股票/商品/加密货币 | 25 请求/天 | [注册](https://www.alphavantage.co/support/#api-key) |

## 功能说明

### 无需 API Key 的功能

以下功能开箱即用，无需任何配置：

- ✅ RSS 新闻抓取（44 个源）
- ✅ 新闻分类
- ✅ 关键词匹配
- ✅ 实体提取
- ✅ 文章去重
- ✅ Web 界面展示

### 需要 API Key 的功能

| 功能 | 需要的 API Key | 说明 |
|------|----------------|------|
| 实时汇率 | `EXCHANGE_RATE_API_KEY` | 165 种货币汇率 |
| 股票数据 | `ALPHA_VANTAGE_API_KEY` | 全球股票市场 |
| 商品价格 | `ALPHA_VANTAGE_API_KEY` | 原油、黄金等 |
| AI 分析 | `DEEPSEEK_API_KEY` | 每日报告、趋势分析 |

## 配置检查

运行配置检查工具，查看当前配置状态：

```bash
python scripts/check_config.py
```

输出示例：

```
============================================================
  Zheye 数据源配置检查报告
============================================================

📡 RSS 数据源
----------------------------------------
  总计: 44 个源
  central_bank: 7 个
  international_org: 3 个
  regional_media: 10 个
  news_media: 24 个

📊 API 数据源
----------------------------------------
  ⚠️ ExchangeRate-API
     汇率数据 (165 种货币)
     免费配额: 1500 请求/月
     注册: https://www.exchangerate-api.com/

  ⚠️ Alpha Vantage
     股票/外汇/商品/加密货币
     免费配额: 25 请求/天
     注册: https://www.alphavantage.co/support/#api-key

🤖 AI 分析配置
----------------------------------------
  ⚠️ DeepSeek API
     注册: https://platform.deepseek.com/
```

## 常见问题

### Q: 没有 API Key 能运行吗？

**A: 可以。** 核心功能（RSS 抓取、分类、关键词匹配）不需要任何 API Key。API 数据源和 AI 分析功能会被自动禁用，不影响其他功能。

### Q: API Key 安全吗？

**A: 安全。** API Key 存储在 `.env` 文件中，该文件已在 `.gitignore` 中排除，不会被提交到代码仓库。

### Q: 如何获取 API Key？

1. **ExchangeRate-API**
   - 访问 https://www.exchangerate-api.com/
   - 注册免费账号
   - 在 Dashboard 获取 API Key

2. **Alpha Vantage**
   - 访问 https://www.alphavantage.co/support/#api-key
   - 填写邮箱，立即获取 API Key

3. **DeepSeek**
   - 访问 https://platform.deepseek.com/
   - 注册账号
   - 在 API Keys 页面创建 Key

### Q: 免费配额够用吗？

对于个人使用或小规模部署，免费配额通常足够：

- **ExchangeRate-API**: 1500 请求/月 ≈ 每天 50 次
- **Alpha Vantage**: 25 请求/天 ≈ 每小时 1 次
- **DeepSeek**: 按 token 计费，每日分析报告消耗很少

## 高级配置

### 自定义 RSS 源

编辑 `scraper/sources/config.yaml`，添加新的 RSS 源：

```yaml
sources:
  - name: Your Source
    type: rss
    url: https://example.com/rss
    lang: en
    weight: 1.5
    category: news_media
```

### 调整抓取频率

在 `.env` 中配置：

```bash
# 抓取超时（秒）
FETCH_TIMEOUT=20

# 重试次数
MAX_RETRIES=2

# 数据保留天数
RETENTION_DAYS=30
```
