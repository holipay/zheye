-- 关键字词库表
CREATE TABLE IF NOT EXISTS keywords (
    id BIGSERIAL PRIMARY KEY,
    term VARCHAR(200) NOT NULL,
    lang VARCHAR(10) NOT NULL DEFAULT 'en',
    category VARCHAR(50) NOT NULL,
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_keyword_term_lang UNIQUE (term, lang)
);

CREATE INDEX IF NOT EXISTS idx_keyword_category ON keywords (category);
CREATE INDEX IF NOT EXISTS idx_keyword_lang ON keywords (lang);

-- 文章-关键字关联表
CREATE TABLE IF NOT EXISTS article_keywords (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    relevance FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_article_keyword UNIQUE (article_id, keyword_id)
);

CREATE INDEX IF NOT EXISTS idx_article_keyword_article ON article_keywords (article_id);
CREATE INDEX IF NOT EXISTS idx_article_keyword_keyword ON article_keywords (keyword_id);

-- 文章-文章关联表
CREATE TABLE IF NOT EXISTS article_relations (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    target_id BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL DEFAULT 'keyword_match',
    score FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_article_relation UNIQUE (source_id, target_id)
);

CREATE INDEX IF NOT EXISTS idx_relation_source ON article_relations (source_id);
CREATE INDEX IF NOT EXISTS idx_relation_target ON article_relations (target_id);
CREATE INDEX IF NOT EXISTS idx_relation_type ON article_relations (relation_type);
CREATE INDEX IF NOT EXISTS idx_relation_score ON article_relations (score DESC);
