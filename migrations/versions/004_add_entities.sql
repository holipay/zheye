-- 实体表
CREATE TABLE IF NOT EXISTS entities (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    normalized_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_entity_normalized UNIQUE (normalized_name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_entity_type ON entities (entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_normalized ON entities (normalized_name);

-- 文章-实体关联表
CREATE TABLE IF NOT EXISTS article_entities (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    entity_id BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    context VARCHAR(500),
    relevance FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_article_entity UNIQUE (article_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_article_entity_article ON article_entities (article_id);
CREATE INDEX IF NOT EXISTS idx_article_entity_entity ON article_entities (entity_id);
