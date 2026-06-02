-- P2: 未来情景推演 - 关键变量 + 观察框架

-- 事件情景推演表
CREATE TABLE IF NOT EXISTS event_scenarios (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- 核心框架
    key_variables JSONB,                     -- 关键变量列表
    observation_signals JSONB,               -- 观察信号清单
    scenarios JSONB,                         -- 情景框架
    thinking_questions JSONB,                -- 思考问题
    
    -- 元数据
    ai_model VARCHAR(50),
    ai_confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_scenarios_event ON event_scenarios (event_id);
