-- 019_add_business_tracker.sql
-- 为企业经营状况贝叶斯跟踪模块添加数据表

-- ============================================================
-- 1. tracked_companies: 要跟踪的企业清单
-- ============================================================
CREATE TABLE IF NOT EXISTS tracked_companies (
    id BIGSERIAL PRIMARY KEY,
    entity_id BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_tracked_entity UNIQUE (entity_id)
);

CREATE INDEX IF NOT EXISTS idx_tracked_companies_active ON tracked_companies (is_active)
    WHERE is_active = TRUE;

-- ============================================================
-- 2. company_dimensions: 每个公司在每个维度上的信念状态
-- ============================================================
CREATE TABLE IF NOT EXISTS company_dimensions (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES tracked_companies(id) ON DELETE CASCADE,
    dimension VARCHAR(50) NOT NULL,
    alpha DOUBLE PRECISION NOT NULL,
    beta DOUBLE PRECISION NOT NULL,
    mean DOUBLE PRECISION NOT NULL,
    variance DOUBLE PRECISION NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(50) DEFAULT 'system',
    CONSTRAINT uq_company_dimension UNIQUE (company_id, dimension)
);

-- ============================================================
-- 3. evidence_records: 每条新闻作为证据的原始记录
-- ============================================================
CREATE TABLE IF NOT EXISTS evidence_records (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES tracked_companies(id) ON DELETE CASCADE,
    news_id BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    dimension VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    strength DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    source VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_evidence_record UNIQUE (news_id, company_id, dimension, source)
);

CREATE INDEX IF NOT EXISTS idx_evidence_company ON evidence_records (company_id, created_at DESC);

-- ============================================================
-- 4. belief_history: 信念状态时间序列快照
-- ============================================================
CREATE TABLE IF NOT EXISTS belief_history (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES tracked_companies(id) ON DELETE CASCADE,
    dimension VARCHAR(50) NOT NULL,
    alpha DOUBLE PRECISION NOT NULL,
    beta DOUBLE PRECISION NOT NULL,
    mean DOUBLE PRECISION NOT NULL,
    variance DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_belief_history_company_dim
    ON belief_history (company_id, dimension, recorded_at ASC);

-- ============================================================
-- 更新 tracked_companies.updated_at 触发器
-- ============================================================
CREATE OR REPLACE FUNCTION update_tracked_companies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tracked_companies_updated_at ON tracked_companies;
CREATE TRIGGER trg_tracked_companies_updated_at
    BEFORE UPDATE ON tracked_companies
    FOR EACH ROW
    EXECUTE FUNCTION update_tracked_companies_updated_at();
