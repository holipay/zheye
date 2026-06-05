"""
共享 Mermaid 图表生成模块
"""

from deep_analyst.models.causal_chain import NodeType


def generate_causal_mermaid(nodes: list, links: list, max_title_len: int = 30, max_desc_len: int = 15) -> str:
    """
    生成因果链的Mermaid流程图语法
    
    Args:
        nodes: 因果节点列表
        links: 因果关系列表
        max_title_len: 标题最大长度
        max_desc_len: 描述最大长度
    
    Returns:
        Mermaid语法字符串
    """
    if not nodes:
        return ""
    
    lines = ["graph LR"]
    
    # 节点ID映射（避免Mermaid语法问题）
    id_map = {}
    for i, node in enumerate(nodes):
        safe_id = f"N{i}"
        id_map[node.id] = safe_id
        
        # 转义特殊字符
        title = node.title.replace('"', "'").replace("[", "(").replace("]", ")")
        if len(title) > max_title_len:
            title = title[:max_title_len - 3] + "..."
        icon = NodeType.get_icon(node.node_type)
        
        # 节点定义
        lines.append(f'    {safe_id}["{icon} {title}"]')
    
    # 关系定义
    link_type_labels = {
        "causes": "导致",
        "enables": "促成",
        "leads_to": "引发",
        "triggers": "触发",
    }
    
    for link in links:
        source_id = id_map.get(link.source_node_id)
        target_id = id_map.get(link.target_node_id)
        
        if source_id and target_id:
            label = link_type_labels.get(link.link_type, "影响")
            if link.description:
                desc = link.description[:max_desc_len].replace('"', "'")
                label = desc
            lines.append(f'    {source_id} -->|{label}| {target_id}')
    
    return "\n".join(lines)
