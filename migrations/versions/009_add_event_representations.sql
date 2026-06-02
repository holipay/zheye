-- P1: 历史类比检索 - 事件多层表征 + 结构化匹配

-- 事件表征表：多层抽象
CREATE TABLE IF NOT EXISTS event_representations (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- 表面层：具体事实
    surface_summary TEXT,                    -- 事件表面概述
    surface_entities JSONB,                  -- 具体实体 ["美联储", "500基点", "2024-01"]
    surface_numbers JSONB,                   -- 关键数字 {"rate_hike_bps": 500}
    
    -- 结构层：因果模式与决策逻辑
    causal_pattern VARCHAR(200),             -- 因果模式标签 "tightening_cycle_inflation_response"
    causal_pattern_desc TEXT,                -- 因果模式描述
    decision_logic TEXT,                     -- 决策者面临的选择结构
    transmission_mechanism TEXT,             -- 传导机制
    constraint_conditions JSONB,             -- 约束条件 ["不可能三角", "资本外流压力"]
    
    -- 抽象层：经济学原理与博弈结构
    economic_principle VARCHAR(200),         -- 经济学原理标签 "impossible_trinity_tradeoff"
    economic_principle_desc TEXT,            -- 原理描述
    game_theory_structure TEXT,              -- 博弈结构描述
    institutional_context TEXT,              -- 制度背景
    
    -- 匹配用向量（可选，用于快速预筛选）
    pattern_embedding JSONB,                 -- 结构模式的向量表示
    
    -- 元数据
    ai_model VARCHAR(50),
    ai_confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_repr_event ON event_representations (event_id);
CREATE INDEX IF NOT EXISTS idx_event_repr_causal ON event_representations (causal_pattern);
CREATE INDEX IF NOT EXISTS idx_event_repr_economic ON event_representations (economic_principle);

-- 历史类比表：存储匹配结果
CREATE TABLE IF NOT EXISTS historical_analogies (
    id BIGSERIAL PRIMARY KEY,
    source_event_id VARCHAR(100) NOT NULL,   -- 当前事件
    target_event_id VARCHAR(100) NOT NULL,   -- 历史事件
    
    -- 匹配维度评分
    causal_similarity FLOAT,                 -- 因果模式相似度
    decision_similarity FLOAT,               -- 决策逻辑相似度
    constraint_similarity FLOAT,             -- 约束条件相似度
    mechanism_similarity FLOAT,              -- 传导机制相似度
    game_similarity FLOAT,                   -- 博弈结构相似度
    overall_similarity FLOAT,                -- 综合相似度
    
    -- 类比描述
    analogy_type VARCHAR(50),                -- structural/pattern/principle
    analogy_summary TEXT,                    -- 类比概述
    key_insight TEXT,                        -- 关键洞察
    lessons_learned TEXT,                    -- 历史教训
    
    -- 差异分析
    surface_differences JSONB,               -- 表面差异
    structural_differences JSONB,            -- 结构差异
    
    -- 元数据
    confidence FLOAT,
    ai_model VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_analogy UNIQUE (source_event_id, target_event_id)
);

CREATE INDEX IF NOT EXISTS idx_analogies_source ON historical_analogies (source_event_id);
CREATE INDEX IF NOT EXISTS idx_analogies_target ON historical_analogies (target_event_id);
CREATE INDEX IF NOT EXISTS idx_analogies_similarity ON historical_analogies (overall_similarity DESC);
