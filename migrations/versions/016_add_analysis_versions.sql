-- 016_add_analysis_versions.sql
-- 添加分析结果版本历史表

-- ============================================================
-- 1. 创建分析版本历史表
-- ============================================================

CREATE TABLE IF NOT EXISTS analysis_versions (
    id BIGSERIAL PRIMARY KEY,
    
    -- 版本标识
    version_number INT NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,  -- article, knowledge, causal, scenario, daily_report
    target_id VARCHAR(200) NOT NULL,  -- 目标ID
    
    -- 分析结果快照
    result_data JSONB NOT NULL,
    
    -- 置信度
    confidence FLOAT,
    
    -- 变更信息
    change_summary TEXT,  -- 变更摘要
    changed_fields JSONB,  -- 变更字段列表 ["sentiment", "summary_zh"]
    previous_version_id BIGINT REFERENCES analysis_versions(id),
    
    -- 元数据
    ai_model VARCHAR(50),
    analysis_duration_ms INT,  -- 分析耗时（毫秒）
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 约束
    UNIQUE(analysis_type, target_id, version_number)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_analysis_versions_target ON analysis_versions (analysis_type, target_id, version_number DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_versions_created ON analysis_versions (created_at DESC);

-- ============================================================
-- 2. 创建版本清理函数（保留最近N个版本）
-- ============================================================

CREATE OR REPLACE FUNCTION cleanup_old_versions(
    p_analysis_type VARCHAR(50),
    p_target_id VARCHAR(200),
    p_keep_count INT DEFAULT 5
)
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    WITH versions_to_delete AS (
        SELECT id
        FROM analysis_versions
        WHERE analysis_type = p_analysis_type
          AND target_id = p_target_id
        ORDER BY version_number DESC
        OFFSET p_keep_count
    )
    DELETE FROM analysis_versions
    WHERE id IN (SELECT id FROM versions_to_delete);
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 3. 创建版本对比函数
-- ============================================================

CREATE OR REPLACE FUNCTION compare_versions(
    p_version_id_1 BIGINT,
    p_version_id_2 BIGINT
)
RETURNS TABLE(
    field_name TEXT,
    old_value JSONB,
    new_value JSONB,
    changed BOOLEAN
) AS $$
DECLARE
    v1_data JSONB;
    v2_data JSONB;
    key TEXT;
BEGIN
    -- 获取两个版本的数据
    SELECT result_data INTO v1_data FROM analysis_versions WHERE id = p_version_id_1;
    SELECT result_data INTO v2_data FROM analysis_versions WHERE id = p_version_id_2;
    
    -- 遍历所有字段进行对比
    FOR key IN SELECT jsonb_object_keys(v1_data) UNION SELECT jsonb_object_keys(v2_data)
    LOOP
        field_name := key;
        old_value := v1_data -> key;
        new_value := v2_data -> key;
        changed := (v1_data -> key) IS DISTINCT FROM (v2_data -> key);
        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 4. 添加自动更新时间触发器
-- ============================================================

CREATE OR REPLACE FUNCTION update_analysis_versions_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.created_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_analysis_versions_timestamp
    BEFORE UPDATE ON analysis_versions
    FOR EACH ROW
    EXECUTE FUNCTION update_analysis_versions_timestamp();
