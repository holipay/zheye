-- P0: 知识模型 - 知识原子 + 事件知识框架

-- 知识原子表：可复用的知识单元
CREATE TABLE IF NOT EXISTS knowledge_atoms (
    id BIGSERIAL PRIMARY KEY,
    atom_type VARCHAR(50) NOT NULL,      -- background/context/history/definition/mechanism
    title VARCHAR(500) NOT NULL,          -- 知识标题（如"什么是基点"）
    content TEXT NOT NULL,                -- 知识内容
    category VARCHAR(50),                 -- 所属领域
    entities JSONB,                       -- 涉及的实体 ["美联储", "通胀"]
    keywords JSONB,                       -- 关联关键词 ["加息", "货币政策"]
    source_article_id BIGINT,             -- 来源文章ID（可选）
    confidence FLOAT DEFAULT 0.8,         -- 置信度
    lang VARCHAR(10) DEFAULT 'zh',        -- 语言
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_atoms_type ON knowledge_atoms (atom_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_atoms_category ON knowledge_atoms (category);
CREATE INDEX IF NOT EXISTS idx_knowledge_atoms_lang ON knowledge_atoms (lang);

-- 事件知识表：事件的知识框架
CREATE TABLE IF NOT EXISTS event_knowledge (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- 知识框架
    background_summary TEXT,              -- 背景概述（AI生成）
    knowledge_gaps JSONB,                 -- 知识缺口列表
    causal_chain JSONB,                   -- 因果链
    key_concepts JSONB,                   -- 关键概念列表
    
    -- 元数据
    ai_model VARCHAR(50),                 -- 使用的AI模型
    ai_confidence FLOAT,                  -- AI分析置信度
    analysis_version INT DEFAULT 1,       -- 分析版本（事件更新时递增）
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 事件-知识原子关联表
CREATE TABLE IF NOT EXISTS event_knowledge_atoms (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL,
    atom_id BIGINT REFERENCES knowledge_atoms(id) ON DELETE CASCADE,
    relevance FLOAT DEFAULT 1.0,          -- 相关性评分
    position INT,                         -- 在知识链中的位置（排序用）
    is_required BOOLEAN DEFAULT true,     -- 是否为必要知识（vs 补充知识）
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_event_atom UNIQUE (event_id, atom_id)
);

CREATE INDEX IF NOT EXISTS idx_event_atoms_event ON event_knowledge_atoms (event_id);
CREATE INDEX IF NOT EXISTS idx_event_atoms_atom ON event_knowledge_atoms (atom_id);
