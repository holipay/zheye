-- 新增正文内容字段
ALTER TABLE news ADD COLUMN IF NOT EXISTS content TEXT;

-- 全文搜索索引（覆盖标题 + 正文）
DROP INDEX IF EXISTS idx_news_fts;
CREATE INDEX IF NOT EXISTS idx_news_fts ON news USING gin (
    to_tsvector('simple', title || ' ' || COALESCE(translated_title, '') || ' ' || COALESCE(content, ''))
);

-- source_health 新增 RSS 条件请求缓存字段
ALTER TABLE source_health ADD COLUMN IF NOT EXISTS last_etag VARCHAR(200);
ALTER TABLE source_health ADD COLUMN IF NOT EXISTS last_rss_modified VARCHAR(200);
