-- 新闻表
CREATE TABLE IF NOT EXISTS news (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    translated_title VARCHAR(500),
    link VARCHAR(1000) NOT NULL,
    link_hash VARCHAR(64) NOT NULL,
    source VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    lang VARCHAR(10) DEFAULT 'en',
    summary TEXT,
    date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_link_hash UNIQUE (link_hash)
);

CREATE INDEX IF NOT EXISTS idx_news_category_date ON news (category, date DESC);
CREATE INDEX IF NOT EXISTS idx_news_source ON news (source);
CREATE INDEX IF NOT EXISTS idx_news_created ON news (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_fts ON news USING gin (
    to_tsvector('simple', title || ' ' || COALESCE(translated_title, ''))
);

-- 分析表
CREATE TABLE IF NOT EXISTS analyses (
    id BIGSERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    analysis TEXT NOT NULL,
    structured JSONB,
    hot_keywords JSONB,
    perspective VARCHAR(50),
    news_count INT DEFAULT 0,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analyses_date ON analyses (date DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_keywords ON analyses USING gin (hot_keywords);

-- 翻译缓存
CREATE TABLE IF NOT EXISTS translation_cache (
    id BIGSERIAL PRIMARY KEY,
    source_text VARCHAR(1000) NOT NULL,
    translated_text VARCHAR(1000) NOT NULL,
    source_hash VARCHAR(64) UNIQUE NOT NULL,
    provider VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_translation_hash ON translation_cache (source_hash);

-- 源健康监控
CREATE TABLE IF NOT EXISTS source_health (
    id BIGSERIAL PRIMARY KEY,
    source_name VARCHAR(100) UNIQUE NOT NULL,
    total_checks INT DEFAULT 0,
    total_success INT DEFAULT 0,
    total_failure INT DEFAULT 0,
    consecutive_failures INT DEFAULT 0,
    last_check TIMESTAMPTZ,
    last_success TIMESTAMPTZ,
    last_error TEXT,
    last_items INT DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0
);

-- 运行指标
CREATE TABLE IF NOT EXISTS run_metrics (
    id BIGSERIAL PRIMARY KEY,
    run_type VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    duration_seconds INT,
    sources_attempted INT DEFAULT 0,
    sources_succeeded INT DEFAULT 0,
    sources_failed INT DEFAULT 0,
    items_fetched INT DEFAULT 0,
    items_deduped INT DEFAULT 0,
    items_final INT DEFAULT 0,
    translate_cached INT DEFAULT 0,
    translate_new INT DEFAULT 0,
    translate_failed INT DEFAULT 0,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_type ON run_metrics (run_type, started_at DESC);

-- 趋势数据
CREATE TABLE IF NOT EXISTS trends (
    id BIGSERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    keywords JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 事件链
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500),
    description TEXT,
    category VARCHAR(50),
    first_seen DATE,
    last_updated DATE,
    update_count INT DEFAULT 1,
    status VARCHAR(20) DEFAULT 'active',
    data JSONB
);

CREATE INDEX IF NOT EXISTS idx_events_status ON events (status, last_updated DESC);
