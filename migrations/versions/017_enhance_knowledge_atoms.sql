-- 017_enhance_knowledge_atoms.sql
-- 增强知识原子表：添加复用统计、版本管理、质量评分

-- ============================================================
-- 1. 添加复用统计字段
-- ============================================================

ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS reuse_count INTEGER DEFAULT 0;
ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS last_reused_at TIMESTAMPTZ;

-- ============================================================
-- 2. 添加版本管理字段
-- ============================================================

ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS previous_version_id BIGINT REFERENCES knowledge_atoms(id) ON DELETE SET NULL;

-- ============================================================
-- 3. 添加质量评分字段
-- ============================================================

ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS quality_score FLOAT DEFAULT 1.0;

-- ============================================================
-- 4. 添加索引
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_knowledge_atoms_quality ON knowledge_atoms (quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_atoms_reuse ON knowledge_atoms (reuse_count DESC);

-- ============================================================
-- 5. 创建 category 关联映射表
-- ============================================================

CREATE TABLE IF NOT EXISTS category_relations (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    related_category VARCHAR(50) NOT NULL,
    relation_strength FLOAT DEFAULT 0.5,  -- 关联强度 0-1
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(category, related_category)
);

-- 插入默认的 category 关联关系
INSERT INTO category_relations (category, related_category, relation_strength) VALUES
    ('央行与利率', '宏观经济', 0.8),
    ('央行与利率', '股市与市场', 0.6),
    ('宏观经济', '央行与利率', 0.8),
    ('宏观经济', '大宗商品与能源', 0.5),
    ('股市与市场', '科技与企业', 0.6),
    ('股市与市场', '央行与利率', 0.6),
    ('大宗商品与能源', '宏观经济', 0.5),
    ('大宗商品与能源', '国际财经', 0.4),
    ('科技与企业', '股市与市场', 0.6),
    ('国际财经', '宏观经济', 0.4),
    ('国际财经', '大宗商品与能源', 0.4)
ON CONFLICT (category, related_category) DO NOTHING;

-- ============================================================
-- 6. 创建知识原子复用统计视图
-- ============================================================

CREATE OR REPLACE VIEW knowledge_atom_stats AS
SELECT 
    ka.id,
    ka.atom_type,
    ka.title,
    ka.category,
    ka.reuse_count,
    ka.quality_score,
    ka.version,
    ka.last_reused_at,
    ka.created_at,
    COUNT(DISTINCT eka.event_id) as event_count
FROM knowledge_atoms ka
LEFT JOIN event_knowledge_atoms eka ON ka.id = eka.atom_id
GROUP BY ka.id;

-- ============================================================
-- 7. 创建质量衰减函数
-- ============================================================

CREATE OR REPLACE FUNCTION update_knowledge_atom_quality()
RETURNS void AS $$
DECLARE
    decay_rate FLOAT := 0.01;  -- 每月衰减率
    min_quality FLOAT := 0.3;  -- 最低质量分
BEGIN
    -- 更新质量评分：考虑复用次数和时间衰减
    UPDATE knowledge_atoms
    SET quality_score = GREATEST(
        min_quality,
        LEAST(1.0, 
            (0.5 + 0.5 * LEAST(reuse_count::FLOAT / 10, 1.0))  -- 复用次数因子（最多10次达到1.0）
            * EXP(-decay_rate * EXTRACT(EPOCH FROM (NOW() - COALESCE(last_reused_at, created_at))) / (30 * 24 * 3600))  -- 时间衰减
        )
    )
    WHERE quality_score > min_quality;  -- 只更新高于最低分的
END;
$$ LANGUAGE plpgsql;