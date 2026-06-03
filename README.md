# 蛰 (Zheye) - 全球新闻聚合与 AI 分析平台

一个面向中文用户的全球金融/科技/社科新闻聚合与 AI 深度分析平台。

## 核心功能

- **新闻聚合**: 从 44+ RSS/API 源自动抓取全球新闻
- **智能处理**: 自动分类、去重、翻译、关键词匹配、实体提取
- **事件追踪**: 自动识别和追踪重大新闻事件
- **AI 分析**: 基于 DeepSeek API 的深度分析（情感分析、每日报告、趋势分析）
- **知识框架**: 事件知识框架构建（知识缺口、因果链、历史类比、情景推演）
- **Web 界面**: 服务端渲染（FastAPI + Jinja2 + HTMX），支持中英文切换
- **管理后台**: RSS 源管理、数据监控、运行日志

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端 | Python 3.10+, FastAPI, SQLAlchemy (async), Alembic |
| 数据库 | PostgreSQL, asyncpg |
| 前端 | Jinja2, HTMX, Chart.js |
| AI | DeepSeek API (OpenAI SDK 兼容) |
| 抓取 | feedparser, httpx, beautifulsoup4, trafilatura |
| 缓存 | cachetools (内存级 TTL 缓存) |
| 调度 | APScheduler / Cron |

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd zheye

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，配置以下必要项：
# - DATABASE_URL: PostgreSQL 连接字符串
# - DEEPSEEK_API_KEY: DeepSeek API 密钥（可选，用于 AI 分析）
# - ADMIN_USERNAME/PASSWORD: 管理后台认证
```

### 3. 初始化数据库

```bash
# 创建数据库
createdb zheye

# 执行迁移脚本
psql -d zheye -f migrations/versions/001_init.sql
psql -d zheye -f migrations/versions/002_add_keywords.sql
psql -d zheye -f migrations/versions/003_add_content.sql
# ... 执行所有迁移脚本
```

### 4. 配置 RSS 源

编辑 `scraper/sources/config.yaml`，添加或修改 RSS 源配置。

### 5. 启动服务

```bash
# 启动 Web 服务
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 运行新闻抓取
python -m scraper.run_news

# 运行每日 AI 分析（可选）
python scripts/run_daily_analysis.py
```

## 项目结构

```
zheye/
├── app/                    # Web 应用层
│   ├── main.py            # FastAPI 入口
│   ├── config.py          # 配置管理
│   ├── context.py         # 模板上下文构建
│   ├── auth.py            # 认证
│   ├── csrf.py            # CSRF 保护
│   ├── cache.py           # 缓存管理
│   ├── i18n.py            # 国际化
│   ├── routes/            # 路由模块
│   │   ├── api_news.py    # 新闻 API
│   │   ├── api_analysis.py # 分析 API
│   │   ├── api_events.py  # 事件 API
│   │   ├── api_common.py  # 共享工具
│   │   ├── pages.py       # 页面路由
│   │   ├── admin.py       # 管理后台
│   │   └── charts.py      # 图表 API
│   ├── templates/         # Jinja2 模板
│   ├── static/            # 静态资源
│   └── locales/           # 国际化文件
├── models/                # 数据模型
├── scraper/               # 数据采集管道
│   ├── sources/           # 数据源配置
│   ├── pipeline/          # 处理管道
│   └── db/                # 数据库操作
├── configs/               # 配置文件
├── migrations/            # 数据库迁移
├── scripts/               # 运维脚本
└── tests/                 # 测试文件
```

## API 端点

### 新闻
- `GET /api/news` - 新闻列表
- `GET /api/news/{id}` - 新闻详情
- `GET /api/search?q=xxx` - 全文搜索
- `GET /api/categories` - 分类列表
- `GET /api/keywords` - 关键词列表

### 分析
- `GET /api/analysis/daily/{date}` - 每日报告
- `GET /api/analysis/weekly/{date}` - 周报
- `GET /api/analysis/monthly/{date}` - 月报
- `GET /api/analysis/sentiment` - 情感统计
- `GET /api/analysis/trends` - 趋势数据

### 事件
- `GET /api/events` - 事件列表
- `GET /api/events/{event_id}` - 事件详情
- `GET /api/events/{event_id}/knowledge` - 知识框架
- `GET /api/events/{event_id}/causal-chain` - 因果链
- `GET /api/events/{event_id}/analogies` - 历史类比
- `GET /api/events/{event_id}/scenarios` - 情景推演

### 管理后台
- `GET /admin` - 管理后台首页
- `GET /admin/api/dashboard` - 仪表盘数据
- `GET /admin/api/sources` - RSS 源管理

## 开发

### 运行测试

```bash
# 运行所有测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=. --cov-report=html

# 运行特定测试文件
pytest tests/test_api.py
```

### 代码质量

```bash
# 代码格式化
black .

# 代码检查
ruff check .

# 类型检查
mypy .
```

## 部署

### 使用 Systemd

```bash
# 创建服务文件
sudo nano /etc/systemd/system/zheye.service

# 启动服务
sudo systemctl enable zheye
sudo systemctl start zheye
```

### 使用 Docker（可选）

```bash
# 构建镜像
docker build -t zheye .

# 运行容器
docker run -d -p 8000:8000 --env-file .env zheye
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
