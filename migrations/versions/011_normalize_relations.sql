-- 迁移脚本：清理重复的双向关系记录
-- 将双向关系合并为单条记录（source_id < target_id）

-- 步骤1: 创建临时表存储规范化后的关系
CREATE TEMP TABLE normalized_relations AS
SELECT 
    LEAST(source_id, target_id) as source_id,
    GREATEST(source_id, target_id) as target_id,
    relation_type,
    MAX(score) as score,
    MIN(created_at) as created_at
FROM article_relations
GROUP BY 
    LEAST(source_id, target_id),
    GREATEST(source_id, target_id),
    relation_type;

-- 步骤2: 删除原有数据
DELETE FROM article_relations;

-- 步骤3: 插入规范化后的数据
INSERT INTO article_relations (source_id, target_id, relation_type, score, created_at)
SELECT source_id, target_id, relation_type, score, created_at
FROM normalized_relations;

-- 步骤4: 删除临时表
DROP TABLE normalized_relations;

-- 步骤5: 更新唯一约束（如果需要）
-- 原有约束 uq_article_relation 应该已经覆盖 (source_id, target_id)

-- 统计结果
SELECT 
    COUNT(*) as total_relations,
    COUNT(DISTINCT source_id) as unique_sources,
    COUNT(DISTINCT target_id) as unique_targets
FROM article_relations;
