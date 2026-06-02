-- P1: 因果链模型 - 多层次因果分析

-- 因果节点表
CREATE TABLE IF NOT EXISTS causal_nodes (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL,           -- 所属事件
    
    -- 节点信息
    node_type VARCHAR(50) NOT NULL,           -- root_cause/trigger/immediate/short_term/long_term/scenario
    title VARCHAR(500) NOT NULL,              -- 节点标题
    description TEXT,                         -- 详细描述
    
    -- 因果属性
    probability FLOAT,                        -- 发生概率 (用于 future_scenarios)
    impact_level VARCHAR(20),                 -- impact: high/medium/low
    time_horizon VARCHAR(50),                 -- 时间维度: immediate/days/weeks/months/years
    
    -- 关联
    evidence JSONB,                           -- 支撑证据（文章ID列表）
    entities JSONB,                           -- 涉及实体
    confidence FLOAT DEFAULT 0.8,             -- 置信度
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_causal_nodes_event ON causal_nodes (event_id);
CREATE INDEX IF NOT EXISTS idx_causal_nodes_type ON causal_nodes (node_type);

-- 因果关系表
CREATE TABLE IF NOT EXISTS causal_links (
    id BIGSERIAL PRIMARY KEY,
    
    -- 关系
    source_node_id BIGINT REFERENCES causal_nodes(id) ON DELETE CASCADE,
    target_node_id BIGINT REFERENCES causal_nodes(id) ON DELETE CASCADE,
    
    -- 关系属性
    link_type VARCHAR(50) DEFAULT 'causes',   -- causes/enables/leads_to/triggers
    strength FLOAT DEFAULT 1.0,               -- 关系强度 0-1
    description TEXT,                         -- 关系描述
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_causal_link UNIQUE (source_node_id, target_node_id)
);

CREATE INDEX IF NOT EXISTS idx_causal_links_source ON causal_links (source_node_id);
CREATE INDEX IF NOT EXISTS idx_causal_links_target ON causal_links (target_node_id);
