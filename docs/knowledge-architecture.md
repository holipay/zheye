# 知识建构系统设计文档

> 文档创建时间：2026-06-03
> 模块状态：P0/P1 已实现，P2 已实现

## 一、核心理念

### 从"信息聚合"到"知识构建"

传统新闻系统：**发生了什么**（What）
知识建构系统：**为什么 → 意味什么 → 会怎样 → 该关注什么**

```
用户获取信息的理想方式：
不是看到碎片化的新闻，而是把碎片知识点编织成结构——
"这件事的起因是什么，经过是什么，可能的走向是什么，各方的逻辑是什么"
```

### 设计原则

1. **赋能而非告知**：提供思考框架，而非标准答案
2. **结构而非表面**：关注因果模式、决策逻辑，而非表面细节
3. **启发而非预测**：帮助用户自己判断，而非给出预测结论
4. **框架而非信息**：识别关键变量，提供观察路径

---

## 二、系统架构

### 整体结构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户视图层                            │
│  事件详情页 → 5个Tab: 知识框架 | 因果链 | 历史类比 | 情景推演 | 时间线  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                        分析引擎层                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ 知识分析 │  │ 因果分析 │  │ 类比分析 │  │ 情景分析 │       │
│  │  (P0)   │  │  (P1)   │  │  (P1)   │  │  (P2)   │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                        数据模型层                            │
│  event_knowledge | causal_nodes | event_representations     │
│  knowledge_atoms | causal_links | historical_analogies      │
│                                              | event_scenarios │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                        数据源层                              │
│  新闻原文 │ 历史事件库 │ AI分析（DeepSeek）                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、P0：知识缺口识别 + 背景补充

### 设计思路

当一个新事件发生时，系统识别"要真正理解这件事，读者需要知道的关键背景知识"。

### 核心组件

| 组件 | 作用 | 示例 |
|------|------|------|
| 知识缺口 | 读者可能缺少的知识点 | "什么是基点"、"该国通胀历史" |
| 背景概述 | 事件的核心背景 | "该国通胀已连续3月超8%" |
| 因果链 | 简化的因果传导 | A→B→C |
| 关键概念 | 术语解释 | "基点：利率计量单位，1基点=0.01%" |
| 知识原子 | 可复用的知识单元 | 背景知识、历史参照、概念解释 |

### 数据模型

```sql
-- 知识原子：可复用的知识单元
knowledge_atoms (
    id, atom_type, title, content, category,
    entities, keywords, lang, confidence
)

-- 事件知识框架
event_knowledge (
    event_id, background_summary, knowledge_gaps,
    causal_chain, key_concepts
)

-- 事件-知识关联
event_knowledge_atoms (event_id, atom_id, relevance, position)
```

### 工作流程

```
新事件 → AI分析知识缺口 → 生成知识框架 → 保存知识原子 → 关联事件
```

---

## 四、P1：因果链构建

### 设计思路

多层次因果结构，从根源到未来走向：

```
根本原因 (root_cause) 🌱  →  深层结构性因素
    ↓
触发因素 (trigger) ⚡      →  直接导火索
    ↓
即时影响 (immediate) 💥    →  直接后果
    ↓
短期效应 (short_term) 📈  →  数天到数周
    ↓
长期走向 (long_term) 🔮    →  数月到数年
    ↓
可能情景 (scenario) 🎯     →  未来可能走向（带概率）
```

### 核心组件

| 节点类型 | 说明 | 时间维度 |
|---------|------|---------|
| root_cause | 根本原因（经济周期、政策框架） | 年 |
| trigger | 触发因素（导火索） | 立即 |
| immediate | 即时影响 | 立即 |
| short_term | 短期效应 | 周 |
| long_term | 长期走向 | 月 |
| scenario | 可能情景 | 月 |

### 数据模型

```sql
-- 因果节点
causal_nodes (
    id, event_id, node_type, title, description,
    probability, impact_level, time_horizon,
    entities, confidence
)

-- 因果关系
causal_links (
    source_node_id, target_node_id,
    link_type, strength, description
)
```

### 关系类型

- `causes`: 导致
- `leads_to`: 引向
- `triggers`: 触发
- `enables`: 促成
- `may_cause`: 可能导致

---

## 五、P1：历史类比检索

### 核心洞察

> 真正的类比是**结构同构**，不是表面相似。

**匹配原则**：找"结构相似但表面不同"的历史事件

| 匹配类型 | 表面层 | 结构层 | 抽象层 | 价值 |
|---------|--------|--------|--------|------|
| 重复 | 相同 | 相同 | 相同 | 低（只是旧闻） |
| **类比** | **不同** | **相似** | **相似** | **高（结构性洞察）** |
| 同义 | 不同 | 不同 | 相同 | 中（原理迁移） |

### 事件的多层表征

```
┌─────────────────────────────────────────────────────────┐
│ 表面层 (Surface)                                          │
│ "某国央行加息500基点"                                      │
│ 具体实体、数字、时间                                       │
├─────────────────────────────────────────────────────────┤
│ 结构层 (Structural)                                       │
│ "央行为应对本币贬值压力，采取超预期紧缩政策"                  │
│ 因果模式、决策逻辑、传导机制                               │
├─────────────────────────────────────────────────────────┤
│ 抽象层 (Abstract)                                         │
│ "在不可能三角约束下，央行牺牲经济增长换取汇率稳定"            │
│ 经济学原理、博弈结构、制度约束                             │
└─────────────────────────────────────────────────────────┘
```

### 匹配维度（加权）

| 维度 | 权重 | 说明 |
|------|------|------|
| 因果模式 | 30% | A→B→C 传导链是否同构 |
| 决策逻辑 | 25% | 决策者选择结构是否相似 |
| 传导机制 | 20% | 影响传导路径是否相同 |
| 约束条件 | 15% | 外部约束是否类似 |
| 博弈结构 | 10% | 多方策略空间是否相似 |

### 匹配策略

1. **规则预筛选**：基于因果模式ID和经济学原理ID快速筛选候选
2. **AI深度分析**：对候选进行详细的类比分析
3. **保存结果**：包括相似度评分、关键洞察、历史教训、差异分析

### 数据模型

```sql
-- 事件多层表征
event_representations (
    event_id,
    -- 表面层
    surface_summary, surface_entities, surface_numbers,
    -- 结构层
    causal_pattern, causal_pattern_desc, decision_logic,
    transmission_mechanism, constraint_conditions,
    -- 抽象层
    economic_principle, economic_principle_desc,
    game_theory_structure, institutional_context
)

-- 历史类比
historical_analogies (
    source_event_id, target_event_id,
    -- 多维度评分
    causal_similarity, decision_similarity,
    constraint_similarity, mechanism_similarity, game_similarity,
    overall_similarity,
    -- 类比描述
    analogy_type, analogy_summary, key_insight, lessons_learned,
    -- 差异分析
    surface_differences, structural_differences
)
```

### 因果模式分类

```python
CAUSAL_PATTERNS = {
    "tightening_cycle_inflation_response": "紧缩周期-通胀应对",
    "easing_cycle_recession_response": "宽松周期-衰退应对",
    "currency_defense_rate_hike": "货币保卫-加息",
    "supply_shock_price_surge": "供给冲击-价格飙升",
    "demand_collapse_policy_stimulus": "需求崩塌-政策刺激",
    "geopolitical_supply_disruption": "地缘政治-供给中断",
    "tech_disruption_industry_reshape": "技术颠覆-行业重塑",
    "financial_contagion_crisis_spread": "金融传染-危机蔓延",
    "regulatory_crackdown_industry_adjust": "监管收紧-行业调整",
    "bust_cycle_deleveraging": "泡沫破裂-去杠杆",
}
```

### 经济学原理分类

```python
ECONOMIC_PRINCIPLES = {
    "impossible_trinity_tradeoff": "不可能三角权衡",
    "taylor_rule_deviation": "泰勒规则偏离",
    "phillips_curve_tradeoff": "菲利普斯曲线权衡",
    "moral_hazard_distortion": "道德风险扭曲",
    "adverse_selection_failure": "逆向选择失败",
    "coordination_failure": "协调失败",
    "bubble_dynamics": "泡沫动态",
    "balance_sheet_recession": "资产负债表衰退",
    "liquidity_trap": "流动性陷阱",
    "currency_crisis_model": "货币危机模型",
}
```

---

## 六、P2：未来情景推演

### 核心理念

> 价值不在于预测准确，而在于启发审视、提供思考结构。

**从"预测"转向"思考框架"**：

```
传统思路：会怎样？→ 给出预测 → 往往错误 → 失去信任
    ↓
新思路：该关注什么？→ 提供框架 → 启发审视 → 赋能判断
```

### 核心组件

| 组件 | 作用 | 不是 |
|------|------|------|
| 关键变量 | 哪些因素会决定走向 | 预测结论 |
| 观察信号 | 该跟踪哪些早期指标 | 确定性判断 |
| 情景框架 | 什么条件下走向A/B/C | 概率预测 |
| 思考问题 | 引导用户自己审视 | 标准答案 |

### 设计原则

1. 关键变量不超过5个，聚焦真正重要的
2. 观察信号具体、可操作
3. 情景框架重在"条件"，不给概率
4. 思考问题能引发真正的思考，不是yes/no问题

### 数据模型

```sql
event_scenarios (
    event_id,
    key_variables,          -- 关键变量列表
    observation_signals,    -- 观察信号清单
    scenarios,              -- 情景框架
    thinking_questions      -- 思考问题
)
```

### 关键变量结构

```json
{
    "name": "变量名称",
    "why_important": "为什么这个变量是关键",
    "current_status": "当前状态",
    "data_source": "如何获取这个数据"
}
```

### 情景框架结构

```json
{
    "name": "情景名称",
    "description": "情景描述",
    "trigger_conditions": ["触发条件1", "触发条件2"],
    "observation_cues": ["观察线索1", "观察线索2"],
    "implications": "如果发生，意味着什么"
}
```

### 思考问题结构

```json
{
    "question": "引导性问题",
    "purpose": "这个问题的目的",
    "perspective": "思考视角（投资者/政策制定者/普通民众/企业主）"
}
```

---

## 七、事件详情页结构

### 5个Tab

```
┌─────────────────────────────────────────────────────────────┐
│  [知识框架]  [因果链]  [历史类比]  [情景推演]  [事件时间线]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Tab 1: 知识框架 (P0)                                       │
│  - 背景概述                                                  │
│  - 知识缺口（理解这件事需要知道什么）                          │
│  - 因果链（简化版）                                           │
│  - 关键概念                                                  │
│  - 背景知识库                                                │
│                                                             │
│  Tab 2: 因果链 (P1)                                         │
│  - 根本原因 → 触发因素 → 即时影响 → 短期效应 → 长期走向       │
│  - 可能情景（带概率）                                         │
│                                                             │
│  Tab 3: 历史类比 (P1)                                       │
│  - 事件模式识别                                              │
│  - 历史类比列表（相似度、关键洞察、历史教训）                   │
│  - 多维度评分（因果/决策/约束/传导/博弈）                      │
│  - 差异分析                                                  │
│                                                             │
│  Tab 4: 情景推演 (P2)                                       │
│  - 关键变量                                                  │
│  - 观察清单                                                  │
│  - 情景框架（触发条件 + 观察线索）                             │
│  - 思考问题                                                  │
│                                                             │
│  Tab 5: 事件时间线                                           │
│  - 相关文章按时间排列                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 八、API 端点

### 知识框架 (P0)

```
GET  /api/events/{event_id}/knowledge?lang={lang}
POST /api/events/{event_id}/knowledge/analyze
```

### 因果链 (P1)

```
GET  /api/events/{event_id}/causal-chain?lang={lang}
POST /api/events/{event_id}/causal-chain/analyze
```

### 历史类比 (P1)

```
GET  /api/events/{event_id}/analogies?lang={lang}
POST /api/events/{event_id}/analogies/analyze
```

### 情景推演 (P2)

```
GET  /api/events/{event_id}/scenarios?lang={lang}
POST /api/events/{event_id}/scenarios/analyze
```

---

## 九、文件索引

### 数据模型

| 文件 | 说明 |
|------|------|
| `models/knowledge.py` | 知识原子、事件知识框架 |
| `models/causal_chain.py` | 因果节点、因果关系 |
| `models/event_representation.py` | 事件多层表征、历史类比 |
| `models/scenario.py` | 情景推演 |

### 分析模块

| 文件 | 说明 |
|------|------|
| `scraper/pipeline/knowledge.py` | P0 知识分析 + P1 因果链分析 |
| `scraper/pipeline/analogy.py` | P1 历史类比检索 |
| `scraper/pipeline/scenario.py` | P2 情景推演 |

### API 路由

| 文件 | 说明 |
|------|------|
| `app/routes/api.py` | 所有知识建构相关 API |

### 前端模板

| 文件 | 说明 |
|------|------|
| `app/templates/partials/event_knowledge.html` | 知识框架展示 |
| `app/templates/partials/knowledge_empty.html` | 知识框架空状态 |
| `app/templates/partials/causal_chain.html` | 因果链展示 |
| `app/templates/partials/causal_chain_empty.html` | 因果链空状态 |
| `app/templates/partials/event_analogies.html` | 历史类比展示 |
| `app/templates/partials/analogy_empty.html` | 历史类比空状态 |
| `app/templates/partials/event_scenarios.html` | 情景推演展示 |
| `app/templates/partials/scenario_empty.html` | 情景推演空状态 |
| `app/templates/partials/event_detail.html` | 事件详情页（含5个Tab） |

### 数据库迁移

| 文件 | 说明 |
|------|------|
| `migrations/versions/007_add_knowledge_models.sql` | P0 知识模型 |
| `migrations/versions/008_add_causal_chain.sql` | P1 因果链 |
| `migrations/versions/009_add_event_representations.sql` | P1 历史类比 |
| `migrations/versions/010_add_event_scenarios.sql` | P2 情景推演 |

---

## 十、未来扩展方向

1. **用户知识图谱**：追踪用户已掌握的知识，个性化推荐
2. **知识原子复用**：跨事件共享背景知识，减少重复生成
3. **实时更新**：事件发展时自动更新因果链和情景框架
4. **多语言支持**：知识原子的中英文关联
5. **社区协作**：用户可以补充和修正知识框架
