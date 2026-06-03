-- 迁移脚本：添加外键约束
-- 为 CausalLink 和 EventKnowledgeAtom 添加外键约束

-- 1. CausalLink: source_node_id -> causal_nodes.id
ALTER TABLE causal_links 
    ADD CONSTRAINT fk_causal_link_source 
    FOREIGN KEY (source_node_id) 
    REFERENCES causal_nodes(id) 
    ON DELETE CASCADE;

-- 2. CausalLink: target_node_id -> causal_nodes.id
ALTER TABLE causal_links 
    ADD CONSTRAINT fk_causal_link_target 
    FOREIGN KEY (target_node_id) 
    REFERENCES causal_nodes(id) 
    ON DELETE CASCADE;

-- 3. EventKnowledgeAtom: event_id -> event_knowledge.event_id
ALTER TABLE event_knowledge_atoms 
    ADD CONSTRAINT fk_event_atom_event 
    FOREIGN KEY (event_id) 
    REFERENCES event_knowledge(event_id) 
    ON DELETE CASCADE;

-- 4. EventKnowledgeAtom: atom_id -> knowledge_atoms.id
ALTER TABLE event_knowledge_atoms 
    ADD CONSTRAINT fk_event_atom_atom 
    FOREIGN KEY (atom_id) 
    REFERENCES knowledge_atoms(id) 
    ON DELETE CASCADE;
