-- 迁移脚本：添加全文搜索索引和 JSONB 索引
-- 提升搜索和查询性能

-- 1. News 表全文搜索索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_news_fts ON news USING gin (
    to_tsvector('simple', 
        title || ' ' || 
        COALESCE(translated_title, '') || ' ' || 
        COALESCE(content, '')
    )
);

-- 2. Events 表 JSONB 索引（event_type 字段）
CREATE INDEX IF NOT EXISTS idx_events_data_type ON events USING gin (
    (data -> 'event_type')
);

-- 3. Events 表状态索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_events_status ON events (status);

-- 4. Events 表更新时间索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_events_last_updated ON events (last_updated DESC);

-- 5. Knowledge atoms 表类型和语言索引
CREATE INDEX IF NOT EXISTS idx_knowledge_atoms_type_lang ON knowledge_atoms (atom_type, lang);

-- 6. Causal nodes 表事件索引
CREATE INDEX IF NOT EXISTS idx_causal_nodes_event_type ON causal_nodes (event_id, node_type);
