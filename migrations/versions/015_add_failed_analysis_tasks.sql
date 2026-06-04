-- 015_add_failed_analysis_tasks.sql
-- 添加失败分析任务队列表

-- ============================================================
-- 1. 创建失败分析任务表
-- ============================================================

CREATE TABLE IF NOT EXISTS failed_analysis_tasks (
    id BIGSERIAL PRIMARY KEY,
    
    -- 任务标识
    task_type VARCHAR(50) NOT NULL,  -- article_analysis, daily_report, keyword_trend, deep_analysis
    target_id VARCHAR(200) NOT NULL,  -- 目标ID（文章ID、日期、关键词等）
    target_type VARCHAR(50),  -- news, event, keyword
    
    -- 任务数据
    input_data JSONB NOT NULL,  -- 原始输入数据（用于重试）
    
    -- 失败信息
    failure_reason VARCHAR(100),  -- api_error, parse_error, low_confidence, timeout, rate_limit
    error_message TEXT,
    error_details JSONB,  -- 详细错误信息
    
    -- 重试配置
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    next_retry_at TIMESTAMPTZ,  -- 下次重试时间
    last_retry_at TIMESTAMPTZ,
    
    -- 状态
    status VARCHAR(20) DEFAULT 'pending',  -- pending, retrying, failed, resolved, abandoned
    
    -- 元数据
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    
    -- 约束
    UNIQUE(task_type, target_id, status)  -- 同一目标同一状态只能有一条记录
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_failed_tasks_status ON failed_analysis_tasks (status, next_retry_at);
CREATE INDEX IF NOT EXISTS idx_failed_tasks_type ON failed_analysis_tasks (task_type, status);
CREATE INDEX IF NOT EXISTS idx_failed_tasks_target ON failed_analysis_tasks (target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_failed_tasks_created ON failed_analysis_tasks (created_at DESC);

-- ============================================================
-- 2. 创建失败任务统计视图
-- ============================================================

CREATE OR REPLACE VIEW failed_analysis_stats AS
SELECT 
    task_type,
    failure_reason,
    status,
    COUNT(*) as task_count,
    AVG(retry_count) as avg_retries,
    MIN(created_at) as earliest_failure,
    MAX(created_at) as latest_failure
FROM failed_analysis_tasks
GROUP BY task_type, failure_reason, status;

-- ============================================================
-- 3. 添加自动更新时间触发器
-- ============================================================

CREATE OR REPLACE FUNCTION update_failed_tasks_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_failed_tasks_timestamp
    BEFORE UPDATE ON failed_analysis_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_failed_tasks_timestamp();
