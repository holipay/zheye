-- 005_add_ai_analysis.sql
-- 添加 AI 分析相关字段和表

-- ============================================================
-- 1. 为 news 表添加 AI 分析字段
-- ============================================================

ALTER TABLE news ADD COLUMN IF NOT EXISTS ai_sentiment VARCHAR(20);
ALTER TABLE news ADD COLUMN IF NOT EXISTS ai_sentiment_score FLOAT;
ALTER TABLE news ADD COLUMN IF NOT EXISTS ai_summary_zh TEXT;
ALTER TABLE news ADD COLUMN IF NOT EXISTS ai_key_points JSONB;
ALTER TABLE news ADD COLUMN IF NOT EXISTS ai_tags JSONB;
ALTER TABLE news ADD COLUMN IF NOT EXISTS ai_importance FLOAT;
ALTER TABLE news ADD COLUMN IF NOT EXISTS ai_analyzed_at TIMESTAMPTZ;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_news_sentiment ON news (ai_sentiment);
CREATE INDEX IF NOT EXISTS idx_news_importance ON news (ai_importance DESC);
CREATE INDEX IF NOT EXISTS idx_news_analyzed ON news (ai_analyzed_at);

-- ============================================================
-- 2. 创建每日分析报告表
-- ============================================================

CREATE TABLE IF NOT EXISTS daily_reports (
    id BIGSERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    overview TEXT,
    hot_topics JSONB,
    market_sentiment VARCHAR(50),
    key_events JSONB,
    trend_analysis TEXT,
    news_count INT DEFAULT 0,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON daily_reports (date DESC);

-- ============================================================
-- 3. 创建趋势数据表
-- ============================================================

CREATE TABLE IF NOT EXISTS trends (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    keyword VARCHAR(100) NOT NULL,
    count INT DEFAULT 0,
    sentiment VARCHAR(20),
    trend VARCHAR(20),  -- rising, stable, declining
    analysis TEXT,
    related_topics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, keyword)
);

CREATE INDEX IF NOT EXISTS idx_trends_date ON trends (date DESC);
CREATE INDEX IF NOT EXISTS idx_trends_keyword ON trends (keyword);
CREATE INDEX IF NOT EXISTS idx_trends_count ON trends (count DESC);

-- ============================================================
-- 4. 创建事件追踪表
-- ============================================================

-- events 表已在 001_init.sql 中创建，这里补充缺失的列
ALTER TABLE events ADD COLUMN IF NOT EXISTS related_articles JSONB;
ALTER TABLE events ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_events_status ON events (status, last_updated DESC);
CREATE INDEX IF NOT EXISTS idx_events_category ON events (category);

-- ============================================================
-- 5. 创建市场数据表（可选，用于存储 API 获取的数据）
-- ============================================================

CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    data_type VARCHAR(20) NOT NULL,  -- forex, commodity, stock, crypto
    symbol VARCHAR(20) NOT NULL,
    value NUMERIC(20, 6) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data (symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_type ON market_data (data_type, timestamp DESC);
