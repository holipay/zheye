-- 迁移脚本：为 source_health 表添加缺失字段
-- 添加 last_etag 和 last_rss_modified 字段

ALTER TABLE source_health ADD COLUMN IF NOT EXISTS last_etag VARCHAR(200);
ALTER TABLE source_health ADD COLUMN IF NOT EXISTS last_rss_modified VARCHAR(200);
