-- 添加 group_id 字段，用于关联中英文关键词
ALTER TABLE keywords ADD COLUMN IF NOT EXISTS group_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_keyword_group_id ON keywords (group_id);
