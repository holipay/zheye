-- 018_seed_historical_events.sql
-- 插入历史事件基础数据，用于历史类比分析

-- ============================================================
-- 1. 紧缩周期-通胀应对 (tightening_cycle_inflation_response)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_volcker_shock_1980',
    '沃尔克加息抗击通胀 (1979-1981)',
    '美联储主席保罗·沃尔克为应对高达13.5%的通胀率，将联邦基金利率从10%提升至20%，引发严重衰退但成功遏制通胀。这是现代货币政策史上最具影响力的紧缩周期之一。',
    '央行与利率',
    '1979-08-01',
    '1981-07-01',
    'historical',
    '{
        "historical": true,
        "era": "1979-1981",
        "region": "美国",
        "key_actors": ["美联储", "保罗·沃尔克"],
        "outcome": "通胀从13.5%降至3.2%，失业率达10.8%",
        "duration_months": 24
    }'::jsonb
),
(
    'hist_fed_2022_hike',
    '美联储激进加息周期 (2022-2023)',
    '为应对40年来最高的通胀率（CPI峰值9.1%），美联储在2022-2023年累计加息525个基点，将联邦基金利率从0-0.25%提升至5.25-5.50%，是40年来最激进的紧缩周期。',
    '央行与利率',
    '2022-03-16',
    '2023-07-26',
    'historical',
    '{
        "historical": true,
        "era": "2022-2023",
        "region": "美国",
        "key_actors": ["美联储", "杰罗姆·鲍威尔"],
        "outcome": "通胀从9.1%降至3%，经济软着陆",
        "duration_months": 17
    }'::jsonb
);

-- ============================================================
-- 2. 宽松周期-衰退应对 (easing_cycle_recession_response)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_gfc_qe_2008',
    '全球金融危机量化宽松 (2008-2014)',
    '2008年次贷危机引发全球金融海啸，美联储将利率降至零附近，并启动三轮量化宽松（QE1-QE3），累计购买约4.5万亿美元资产，开创了非常规货币政策时代。',
    '央行与利率',
    '2008-11-25',
    '2014-10-29',
    'historical',
    '{
        "historical": true,
        "era": "2008-2014",
        "region": "美国",
        "key_actors": ["美联储", "本·伯南克"],
        "outcome": "金融系统稳定，经济缓慢复苏，失业率从10%降至5.9%",
        "duration_months": 72
    }'::jsonb
),
(
    'hist_covid_stimulus_2020',
    '新冠疫情大规模刺激政策 (2020)',
    '新冠疫情引发全球性经济停摆，美联储紧急降息至零并启动无限量QE，同时美国政府推出约5万亿美元财政刺激，包括直接发放现金、加强失业救济和企业救助。',
    '央行与利率',
    '2020-03-15',
    '2020-12-31',
    'historical',
    '{
        "historical": true,
        "era": "2020",
        "region": "全球",
        "key_actors": ["美联储", "美国财政部", "国会"],
        "outcome": "经济快速V型复苏，但埋下通胀隐患",
        "duration_months": 10
    }'::jsonb
);

-- ============================================================
-- 3. 货币保卫-加息 (currency_defense_rate_hike)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_asian_crisis_1997',
    '亚洲金融危机货币保卫战 (1997-1998)',
    '泰铢崩溃引发亚洲金融危机，泰国、印尼、韩国等国货币大幅贬值。为捍卫汇率，多国被迫大幅加息，香港甚至将隔夜利率提升至300%。最终依靠IMF救助和结构性改革走出危机。',
    '国际财经',
    '1997-07-02',
    '1998-10-01',
    'historical',
    '{
        "historical": true,
        "era": "1997-1998",
        "region": "亚洲",
        "key_actors": ["泰国央行", "IMF", "香港金管局"],
        "outcome": "货币大幅贬值，多国经济衰退，联系汇率制维持",
        "duration_months": 15
    }'::jsonb
),
(
    'hist_jpy_intervention_2022',
    '日本央行日元保卫战 (2022)',
    '日元兑美元贬值至32年低点（151.94），日本财务省进行1998年以来首次外汇干预，投入约600亿美元买入日元。同时日本央行维持超宽松政策，形成政策分化。',
    '国际财经',
    '2022-09-22',
    '2022-10-24',
    'historical',
    '{
        "historical": true,
        "era": "2022",
        "region": "日本",
        "key_actors": ["日本财务省", "日本央行"],
        "outcome": "短期稳定汇率，但日元继续承压",
        "duration_months": 2
    }'::jsonb
);

-- ============================================================
-- 4. 供给冲击-价格飙升 (supply_shock_price_surge)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_oil_crisis_1973',
    '第一次石油危机 (1973-1974)',
    '第四次中东战争爆发，OPEC对支持以色列的国家实施石油禁运，油价从每桶3美元飙升至12美元（涨幅300%），引发全球性滞胀和经济衰退，彻底改变了能源地缘政治格局。',
    '大宗商品与能源',
    '1973-10-17',
    '1974-03-18',
    'historical',
    '{
        "historical": true,
        "era": "1973-1974",
        "region": "全球",
        "key_actors": ["OPEC", "沙特阿拉伯", "阿拉伯产油国"],
        "outcome": "油价翻4倍，全球通胀高企，经济衰退",
        "duration_months": 5
    }'::jsonb
),
(
    'hist_russia_ukraine_energy_2022',
    '俄乌冲突能源危机 (2022)',
    '俄罗斯入侵乌克兰引发全球能源危机，欧洲天然气价格飙升10倍，布伦特原油突破130美元/桶。欧盟加速能源转型并实施石油禁运，全球能源供应链深度重构。',
    '大宗商品与能源',
    '2022-02-24',
    '2022-08-01',
    'historical',
    '{
        "historical": true,
        "era": "2022",
        "region": "欧洲",
        "key_actors": ["俄罗斯", "欧盟", "OPEC+"],
        "outcome": "能源价格暴涨，欧洲能源安全战略重塑",
        "duration_months": 6
    }'::jsonb
);

-- ============================================================
-- 5. 需求崩塌-政策刺激 (demand_collapse_policy_stimulus)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_lehman_collapse_2008',
    '雷曼兄弟倒闭与全球救市 (2008)',
    '2008年9月15日雷曼兄弟申请破产，引发全球金融市场恐慌性抛售。美国政府被迫推出7000亿美元TARP计划，全球央行协同降息，开启了史无前例的政策干预时代。',
    '股市与市场',
    '2008-09-15',
    '2008-10-03',
    'historical',
    '{
        "historical": true,
        "era": "2008",
        "region": "全球",
        "key_actors": ["美联储", "美国财政部", "全球央行"],
        "outcome": "全球股市暴跌40%，信贷市场冻结，政策大幅转向",
        "duration_months": 1
    }'::jsonb
),
(
    'hist_covid_lockdown_2020',
    '新冠疫情封锁与全球刺激 (2020)',
    '新冠疫情导致全球性经济封锁，美国单周失业人数飙升至660万，全球股市暴跌30%。各国推出总计超10万亿美元财政刺激，美联储两周内扩表1万亿美元。',
    '宏观经济',
    '2020-03-11',
    '2020-04-01',
    'historical',
    '{
        "historical": true,
        "era": "2020",
        "region": "全球",
        "key_actors": ["各国政府", "各国央行"],
        "outcome": "经济V型反弹，但通胀压力累积",
        "duration_months": 1
    }'::jsonb
);

-- ============================================================
-- 6. 地缘政治-供给中断 (geopolitical_supply_disruption)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_iran_revolution_1979',
    '伊朗革命与第二次石油危机 (1979-1980)',
    '伊朗伊斯兰革命推翻巴列维王朝，伊朗石油出口几乎中断。随后两伊战争爆发，两国石油产能大幅下降。油价从14美元/桶飙升至39美元/桶，引发全球第二波滞胀。',
    '大宗商品与能源',
    '1979-01-16',
    '1980-09-22',
    'historical',
    '{
        "historical": true,
        "era": "1979-1980",
        "region": "中东",
        "key_actors": ["伊朗", "伊拉克", "OPEC"],
        "outcome": "油价翻近3倍，全球通胀再起，沃尔克加息",
        "duration_months": 20
    }'::jsonb
),
(
    'hist_russia_ukraine_2022',
    '俄乌冲突与全球供应链冲击 (2022)',
    '2022年2月24日俄罗斯全面入侵乌克兰，引发二战后欧洲最大规模军事冲突。西方对俄实施史无前例制裁，俄罗斯能源、粮食、金属出口受阻，全球大宗商品价格暴涨。',
    '国际财经',
    '2022-02-24',
    '2022-03-01',
    'historical',
    '{
        "historical": true,
        "era": "2022",
        "region": "欧洲",
        "key_actors": ["俄罗斯", "乌克兰", "北约", "欧盟"],
        "outcome": "能源粮食价格暴涨，全球通胀加剧，地缘格局重塑",
        "duration_months": 1
    }'::jsonb
);

-- ============================================================
-- 7. 技术颠覆-行业重塑 (tech_disruption_industry_reshape)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_dotcom_bubble_2000',
    '互联网泡沫破裂 (2000-2002)',
    '纳斯达克指数从5048点高点暴跌78%至1114点，大量互联网公司破产。亚马逊股价跌去93%，Pets.com等明星公司倒闭。标志着第一轮互联网狂热的终结，但也奠定了后续数字经济发展基础。',
    '科技与企业',
    '2000-03-10',
    '2002-10-09',
    'historical',
    '{
        "historical": true,
        "era": "2000-2002",
        "region": "美国",
        "key_actors": ["纳斯达克", "互联网公司", "风投"],
        "outcome": "纳指暴跌78%，万亿市值蒸发，行业洗牌",
        "duration_months": 30
    }'::jsonb
),
(
    'hist_ai_revolution_2023',
    '生成式AI革命 (2023)',
    'ChatGPT引爆生成式AI热潮，英伟达市值突破万亿美元，科技巨头竞相布局AI。AI正在重塑软件开发、内容创作、医疗研发等行业，被视为继互联网后最大的技术变革。',
    '科技与企业',
    '2023-01-01',
    '2023-12-31',
    'historical',
    '{
        "historical": true,
        "era": "2023",
        "region": "全球",
        "key_actors": ["OpenAI", "英伟达", "微软", "谷歌"],
        "outcome": "AI概念股暴涨，行业加速转型，监管讨论升温",
        "duration_months": 12
    }'::jsonb
);

-- ============================================================
-- 8. 金融传染-危机蔓延 (financial_contagion_crisis_spread)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_asian_flu_1997',
    '亚洲金融危机传染 (1997-1998)',
    '泰铢贬值引发连锁反应，危机从泰国蔓延至马来西亚、印尼、韩国、香港、俄罗斯。新兴市场货币竞相贬值，资本大规模外逃，全球金融体系面临系统性风险。',
    '国际财经',
    '1997-07-02',
    '1998-08-17',
    'historical',
    '{
        "historical": true,
        "era": "1997-1998",
        "region": "新兴市场",
        "key_actors": ["IMF", "世界银行", "各国央行"],
        "outcome": "多国货币崩溃，经济衰退，社会动荡",
        "duration_months": 13
    }'::jsonb
),
(
    'hist_subprime_2008',
    '次贷危机全球传染 (2007-2009)',
    '美国次贷危机演变为全球金融海啸，欧洲银行因持有大量MBS资产而巨亏，冰岛银行体系崩溃，雷曼倒闭引发全球信贷冻结。危机从金融市场传导至实体经济，引发大萧条以来最严重衰退。',
    '股市与市场',
    '2007-08-01',
    '2009-03-09',
    'historical',
    '{
        "historical": true,
        "era": "2007-2009",
        "region": "全球",
        "key_actors": ["华尔街投行", "美联储", "欧洲央行"],
        "outcome": "全球股市暴跌，银行倒闭潮，经济大衰退",
        "duration_months": 19
    }'::jsonb
);

-- ============================================================
-- 9. 监管收紧-行业调整 (regulatory_crackdown_industry_adjust)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_china_edu_2021',
    '中国教培行业监管风暴 (2021)',
    '2021年7月中国出台"双减"政策，禁止学科类培训机构上市融资和资本化运作。新东方、好未来等龙头股价暴跌90%以上，行业市值蒸发超万亿，数百万从业者受影响。',
    '科技与企业',
    '2021-07-24',
    '2021-12-31',
    'historical',
    '{
        "historical": true,
        "era": "2021",
        "region": "中国",
        "key_actors": ["国务院", "教育部", "教培企业"],
        "outcome": "行业规模缩减90%，企业被迫转型，就业冲击",
        "duration_months": 5
    }'::jsonb
),
(
    'hist_crypto_crackdown_2023',
    '加密货币监管收紧 (2023)',
    'FTX倒闭后全球加密监管加速，SEC起诉币安和Coinbase，欧盟实施MiCA框架，香港推出持牌交易所制度。行业从野蛮生长转向合规化，机构资金加速入场。',
    '科技与企业',
    '2023-01-01',
    '2023-12-31',
    'historical',
    '{
        "historical": true,
        "era": "2023",
        "region": "全球",
        "key_actors": ["SEC", "币安", "Coinbase"],
        "outcome": "行业合规化，交易所洗牌，机构采用加速",
        "duration_months": 12
    }'::jsonb
);

-- ============================================================
-- 10. 泡沫破裂-去杠杆 (bust_cycle_deleveraging)
-- ============================================================

INSERT INTO events (event_id, title, description, category, first_seen, last_updated, status, data) VALUES
(
    'hist_japan_bubble_1990',
    '日本泡沫经济破裂 (1990-2000)',
    '日经指数从38957点历史高点暴跌，东京地价跌去70%。企业资产负债表衰退，银行坏账堆积，经济陷入"失落的十年"。日本央行零利率政策未能有效刺激需求，成为流动性陷阱的经典案例。',
    '股市与市场',
    '1989-12-29',
    '2000-01-01',
    'historical',
    '{
        "historical": true,
        "era": "1990-2000",
        "region": "日本",
        "key_actors": ["日本央行", "日本企业", "银行"],
        "outcome": "股市跌70%，地价跌70%，经济长期停滞",
        "duration_months": 120
    }'::jsonb
),
(
    'hist_us_housing_2008',
    '美国房地产泡沫破裂 (2006-2012)',
    '美国房价在经历十年上涨后崩盘，全国平均房价跌去33%，拉斯维加斯、凤凰城等热点城市跌幅超50%。次贷违约引发连锁反应，最终导致雷曼倒闭和全球金融危机。',
    '宏观经济',
    '2006-07-01',
    '2012-02-01',
    'historical',
    '{
        "historical": true,
        "era": "2006-2012",
        "region": "美国",
        "key_actors": ["房利美", "房地美", "华尔街银行"],
        "outcome": "房价跌33%，止赎潮，次贷危机，全球金融海啸",
        "duration_months": 67
    }'::jsonb
);

-- ============================================================
-- 2. 插入事件表征数据 (用于结构化匹配)
-- ============================================================

-- 沃尔克加息
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_volcker_shock_1980',
    '美联储大幅加息至20%以遏制两位数通胀',
    '["美联储", "保罗·沃尔克", "联邦基金利率", "CPI"]'::jsonb,
    '{"rate_peak": 20, "inflation_peak": 13.5, "unemployment_peak": 10.8}'::jsonb,
    'tightening_cycle_inflation_response',
    '面对持续高通胀，央行采取强力紧缩政策，通过大幅提高利率抑制需求，即使引发衰退也要恢复物价稳定',
    '沃尔克选择以经济衰退为代价抗击通胀，因为此前渐进式加息已被证明无效，必须采取激进措施打破通胀预期',
    '高利率→融资成本上升→投资消费下降→需求收缩→通胀回落→但同时引发衰退和失业',
    '["通胀预期脱锚", "渐进式政策失败", "政治压力"]'::jsonb,
    'taylor_rule_deviation',
    '当通胀远超目标时，央行需要大幅提高实际利率至中性水平以上，即使短期付出经济代价',
    'system',
    0.95
);

-- 2022美联储加息
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_fed_2022_hike',
    '美联储40年来最激进加息周期，累计加息525基点',
    '["美联储", "杰罗姆·鲍威尔", "联邦基金利率", "CPI"]'::jsonb,
    '{"rate_hike_bps": 525, "inflation_peak": 9.1, "final_rate": 5.5}'::jsonb,
    'tightening_cycle_inflation_response',
    '疫情后大规模财政货币刺激叠加供应链冲击，通胀飙升至40年高位，美联储被迫启动激进紧缩周期',
    '鲍威尔选择快速大幅加息而非渐进式，因为通胀已远超2%目标且劳动力市场极度紧张，需要快速抑制需求',
    '快速加息→金融条件收紧→需求降温→供应链恢复→通胀逐步回落→实现罕见的软着陆',
    '["通胀远超目标", "劳动力市场紧张", "供应链瓶颈"]'::jsonb,
    'taylor_rule_deviation',
    '当通胀远超目标且就业强劲时，央行需要快速将利率提升至限制性水平',
    'system',
    0.95
);

-- 2008金融危机QE
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_gfc_qe_2008',
    '美联储零利率+三轮QE购买4.5万亿美元资产',
    '["美联储", "本·伯南克", "QE1", "QE2", "QE3", "MBS", "国债"]'::jsonb,
    '{"total_qe_trillion": 4.5, "rate_lower_bound": 0, "unemployment_peak": 10}'::jsonb,
    'easing_cycle_recession_response',
    '次贷危机引发全球金融海啸，传统货币政策失效（零利率下限），央行被迫采取非常规量化宽松政策',
    '伯南克选择QE是因为利率已降至零无法继续降息，需要通过购买长期资产来压低长端利率和风险溢价',
    'QE购买→长端利率下降→资产价格上升→财富效应→借贷成本下降→投资消费恢复→经济复苏',
    '["零利率下限", "流动性陷阱", "信贷市场冻结"]'::jsonb,
    'liquidity_trap',
    '当利率降至零下限时，传统货币政策失效，央行需要通过资产购买直接影响长端利率和金融条件',
    'system',
    0.95
);

-- 亚洲金融危机
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_asian_crisis_1997',
    '泰铢崩溃引发亚洲金融危机，多国货币大幅贬值',
    '["泰铢", "韩元", "印尼盾", "IMF", "香港金管局"]'::jsonb,
    '{"thb_depreciation": -50, "krw_depreciation": -40, "idr_depreciation": -80}'::jsonb,
    'currency_defense_rate_hike',
    '固定汇率制下资本账户开放，外部冲击引发资本外逃，央行被迫大幅加息捍卫汇率但效果有限',
    '泰国等国选择加息是因为放弃固定汇率将导致银行体系崩溃（外债过高），必须保卫汇率',
    '资本外逃→外汇储备下降→加息吸引资本→但经济衰退加剧→最终被迫放弃固定汇率→货币暴跌',
    '["固定汇率制", "资本账户开放", "外债过高"]'::jsonb,
    'impossible_trinity_tradeoff',
    '固定汇率、资本自由流动、独立货币政策三者不可兼得，危机国家被迫放弃汇率稳定',
    'system',
    0.95
);

-- 石油危机
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_oil_crisis_1973',
    'OPEC石油禁运导致油价暴涨300%',
    '["OPEC", "沙特阿拉伯", "石油", "阿拉伯产油国"]'::jsonb,
    '{"oil_price_increase": 300, "oil_price_from": 3, "oil_price_to": 12}'::jsonb,
    'supply_shock_price_surge',
    '地缘政治冲突导致能源供给突然中断，价格暴涨传导至整个经济体系，引发成本推动型通胀',
    'OPEC选择禁运是为了政治目的（迫使以色列撤军），但经济手段成为地缘政治武器',
    '石油禁运→供给收缩→油价暴涨→生产成本上升→全面通胀→经济衰退（滞胀）',
    '["地缘政治冲突", "能源依赖", "供给弹性低"]'::jsonb,
    'supply_shock_price_surge',
    '供给冲击导致价格暴涨时，传统需求管理政策陷入两难：紧缩抗通胀会加剧衰退，宽松保增长会加剧通胀',
    'system',
    0.95
);

-- 互联网泡沫
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_dotcom_bubble_2000',
    '纳斯达克指数暴跌78%，互联网泡沫破裂',
    '["纳斯达克", "互联网公司", "风投", "亚马逊", "Pets.com"]'::jsonb,
    '{"nasdaq_peak": 5048, "nasdaq_trough": 1114, "decline_pct": 78}'::jsonb,
    'bust_cycle_deleveraging',
    '投机狂热推高科技股估值至不可持续水平，当盈利预期无法兑现时泡沫破裂，引发去杠杆和资产价格螺旋下跌',
    '投资者在非理性繁荣中追涨，忽视基本面，当部分公司破产暴露行业问题时引发恐慌性抛售',
    '投机狂热→估值泡沫→盈利不及预期→信心崩溃→抛售潮→流动性枯竭→资产价格螺旋下跌→实体经济衰退',
    '["非理性繁荣", "估值脱离基本面", "投机杠杆"]'::jsonb,
    'bubble_dynamics',
    '泡沫的形成和破裂遵循相似模式：过度乐观→杠杆上升→价格加速→触发因素→恐慌抛售→去杠杆',
    'system',
    0.95
);

-- 次贷危机
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_subprime_2008',
    '美国次贷危机演变为全球金融海啸',
    '["次级贷款", "MBS", "CDO", "雷曼兄弟", "AIG", "美联储"]'::jsonb,
    '{"sp500_decline": -57, "gdp_decline": -4.3, "unemployment_peak": 10}'::jsonb,
    'financial_contagion_crisis_spread',
    '美国房地产泡沫破裂引发次贷违约，通过复杂金融衍生品传导至全球银行体系，导致系统性金融危机',
    '银行过度追求收益忽视风险，监管放松允许高杠杆，当房价下跌时整个金融体系面临连锁违约',
    '房价下跌→次贷违约→MBS/CDO减值→银行巨亏→信贷收缩→实体经济衰退→更多违约→危机螺旋',
    '["金融衍生品复杂性", "监管缺失", "高杠杆", "全球化"]'::jsonb,
    'moral_hazard_distortion',
    '政府隐性担保导致金融机构过度冒险，"大而不能倒"问题加剧道德风险',
    'system',
    0.95
);

-- 日本泡沫
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_japan_bubble_1990',
    '日本泡沫经济破裂，开启失落的十年',
    '["日经指数", "东京地价", "日本央行", "银行坏账"]'::jsonb,
    '{"nikkei_peak": 38957, "nikkei_decline_pct": -80, "land_price_decline_pct": -70}'::jsonb,
    'bust_cycle_deleveraging',
    '宽松货币环境催生资产价格泡沫，当央行收紧货币政策时泡沫破裂，企业资产负债表衰退导致长期经济停滞',
    '日本央行选择主动刺破泡沫是因为担心金融稳定，但紧缩时机和力度把握不当导致硬着陆',
    '宽松货币→资产泡沫→央行收紧→泡沫破裂→资产价格暴跌→企业资不抵债→资产负债表衰退→通缩螺旋',
    '["资产泡沫", "高杠杆", "银行体系坏账"]'::jsonb,
    'balance_sheet_recession',
    '当企业资产大幅缩水陷入负净值时，即使利率为零也会优先偿债而非借贷，导致需求长期不足',
    'system',
    0.95
);

-- 新冠疫情刺激
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_covid_stimulus_2020',
    '新冠疫情引发全球封锁和史无前例的政策刺激',
    '["美联储", "国会", "财政刺激", "失业救济"]'::jsonb,
    '{"fiscal_stimulus_trillion": 5, "unemployment_peak": 14.7, "fed_balance_sheet_increase": 3}'::jsonb,
    'demand_collapse_policy_stimulus',
    '疫情封锁导致需求突然崩塌，经济陷入人为衰退，政府被迫采取超大规模财政货币刺激防止经济萧条',
    '政府选择超大规模刺激是因为危机性质特殊（外生冲击非内生失衡），需要快速托底避免连锁反应',
    '疫情封锁→经济停摆→需求崩塌→大规模刺激→需求快速恢复→供应链瓶颈→通胀上升',
    '["外生冲击", "供应链中断", "劳动力市场摩擦"]'::jsonb,
    'demand_collapse_policy_stimulus',
    '外生冲击导致的需求崩塌需要大规模政策刺激，但刺激规模和退出时机需要精确把握',
    'system',
    0.95
);

-- 俄乌冲突
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_russia_ukraine_2022',
    '俄乌冲突引发全球能源粮食危机和地缘格局重塑',
    '["俄罗斯", "乌克兰", "欧盟", "NATO", "天然气", "小麦"]'::jsonb,
    '{"gas_price_increase": 1000, "wheat_price_increase": 50, "oil_price_peak": 130}'::jsonb,
    'geopolitical_supply_disruption',
    '大国军事冲突引发西方制裁，俄罗斯能源粮食出口受阻，全球供应链面临地缘政治冲击',
    '西方选择严厉制裁是因为地缘政治考量（遏制俄罗斯），但承受了巨大的经济代价（高通胀）',
    '军事冲突→西方制裁→俄罗斯供给减少→能源粮食价格暴涨→全球通胀加剧→经济增长放缓',
    '["地缘政治冲突", "能源依赖", "粮食安全"]'::jsonb,
    'geopolitical_supply_disruption',
    '地缘政治冲突引发的供给冲击难以通过传统政策应对，需要结构性调整（能源转型、供应链多元化）',
    'system',
    0.95
);

-- 伊朗革命
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_iran_revolution_1979',
    '伊朗革命引发第二次石油危机',
    '["伊朗", "伊拉克", "OPEC", "石油"]'::jsonb,
    '{"oil_price_increase": 178, "oil_price_from": 14, "oil_price_to": 39}'::jsonb,
    'geopolitical_supply_disruption',
    '政权更迭导致石油出口中断，随后两伊战争进一步削减产能，引发全球第二波能源危机',
    '伊朗革命是内部政治变动，但石油武器化加剧了地缘政治对能源市场的冲击',
    '政治革命→石油出口中断→供给收缩→油价暴涨→全球通胀→经济衰退',
    '["政权更迭", "战争冲突", "能源依赖"]'::jsonb,
    'geopolitical_supply_disruption',
    '政治不稳定导致的供给中断具有突发性和不可预测性，需要建立战略储备和多元化供应',
    'system',
    0.95
);

-- 中国教培监管
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_china_edu_2021',
    '中国教培行业"双减"政策引发行业地震',
    '["国务院", "教育部", "新东方", "好未来", "教培机构"]'::jsonb,
    '{"industry_decline_pct": -90, "stock_price_decline_pct": -95}'::jsonb,
    'regulatory_crackdown_industry_adjust',
    '政府为减轻家庭负担和教育焦虑，出台严厉监管政策禁止学科类教培资本化运作，行业规模急剧萎缩',
    '政府选择一刀切监管是因为行业过度资本化加剧教育内卷，需要强力矫正',
    '政策出台→行业禁止资本化→机构倒闭→从业者失业→相关产业链受损→行业转型',
    '["社会政策目标", "资本无序扩张", "民生保障"]'::jsonb,
    'regulatory_crackdown_industry_adjust',
    '政府监管可以在短时间内重塑行业格局，企业需要将监管风险纳入战略考量',
    'system',
    0.95
);

-- 亚洲金融危机传染
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_asian_flu_1997',
    '亚洲金融危机从泰国蔓延至整个新兴市场',
    '["泰铢", "韩元", "印尼盾", "IMF", "资本外逃"]'::jsonb,
    '{"affected_countries": 8, "imf_bailout_billion": 100}'::jsonb,
    'financial_contagion_crisis_spread',
    '一国货币危机通过贸易联系、金融关联和信心渠道传染至邻国，形成区域性金融危机',
    '危机传染是因为新兴市场国家经济结构相似且存在贸易竞争关系，一国贬值削弱他国竞争力',
    '泰铢贬值→竞争性贬值→资本外逃→银行危机→信贷收缩→经济衰退→更多国家陷入危机',
    '["经济结构相似", "贸易竞争", "资本流动"]'::jsonb,
    'financial_contagion_crisis_spread',
    '金融传染具有自我实现特征，需要建立区域金融安全网和危机预警机制',
    'system',
    0.95
);

-- 房地产泡沫
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_us_housing_2008',
    '美国房地产泡沫破裂引发全球金融危机',
    '["房利美", "房地美", "次级贷款", "华尔街"]'::jsonb,
    '{"home_price_decline_pct": -33, "foreclosure_millions": 3.8}'::jsonb,
    'bust_cycle_deleveraging',
    '宽松信贷和金融创新催生房地产泡沫，当房价下跌时次贷违约引发连锁反应，最终导致全球金融海啸',
    '银行和借款人过度乐观，认为房价只涨不跌，忽视了系统性风险',
    '房价上涨→信贷扩张→投机需求→房价泡沫→利率上升→房价下跌→违约潮→金融机构巨亏→信贷冻结',
    '["信贷泡沫", "金融创新", "监管缺失"]'::jsonb,
    'bust_cycle_deleveraging',
    '资产泡沫破裂后的去杠杆过程漫长痛苦，需要政策干预防止螺旋式下跌',
    'system',
    0.95
);

-- 日元干预
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_jpy_intervention_2022',
    '日本央行干预汇市保卫日元',
    '["日本财务省", "日本央行", "日元", "美元"]'::jsonb,
    '{"jpy_low": 151.94, "intervention_billion_usd": 60}'::jsonb,
    'currency_defense_rate_hike',
    '日元大幅贬值至32年低点，日本财务省进行外汇干预买入日元，但央行维持超宽松政策形成矛盾',
    '日本选择干预是因为日元过度贬值损害消费者购买力，但不愿收紧货币政策影响经济复苏',
    '日美利差扩大→资本外流→日元贬值→进口成本上升→通胀压力→央行干预→短期稳定→但利差持续→日元继续承压',
    '["货币政策分化", "利差驱动", "通胀压力"]'::jsonb,
    'currency_defense_rate_hike',
    '汇率干预在利差持续存在时效果有限，需要货币政策配合才能有效稳定汇率',
    'system',
    0.95
);

-- AI革命
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_ai_revolution_2023',
    '生成式AI革命重塑科技行业和工作方式',
    '["OpenAI", "ChatGPT", "英伟达", "微软", "谷歌"]'::jsonb,
    '{"nvda_market_cap_trillion": 1, "chatgpt_users_million": 100}'::jsonb,
    'tech_disruption_industry_reshape',
    '生成式AI突破引发科技行业新一轮变革，AI能力快速提升正在重塑软件、内容、医疗等多个行业',
    '科技巨头竞相布局AI是因为认识到这是继互联网、移动互联网后最大的技术范式转换',
    'AI技术突破→产品化应用→行业效率提升→部分岗位被替代→新岗位出现→经济结构转型',
    '["技术突破", "资本涌入", "人才竞争"]'::jsonb,
    'tech_disruption_industry_reshape',
    '颠覆性技术往往经历炒作-泡沫-洗牌-成熟的过程，长期影响深远但短期可能过热',
    'system',
    0.95
);

-- 金融传染（2008）
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_gfc_contagion_2008',
    '次贷危机通过金融衍生品传染至全球银行体系',
    '["MBS", "CDO", "CDS", "AIG", "欧洲银行"]'::jsonb,
    '{"global_bank_writeoff_trillion": 2, "lehman_bonds_recovery_pct": 0}'::jsonb,
    'financial_contagion_crisis_spread',
    '美国次贷损失通过复杂金融衍生品传导至全球银行，欧洲银行因持有大量有毒资产而巨亏，危机从美国蔓延至全球',
    '银行通过证券化转移风险但未消除系统性风险，反而使风险更加隐蔽和复杂',
    '美国房价下跌→次贷违约→MBS减值→CDO崩溃→持有银行巨亏→信贷收缩→全球金融恐慌',
    '["金融衍生品复杂性", "全球化", "系统性风险"]'::jsonb,
    'financial_contagion_crisis_spread',
    '金融创新可以分散但不能消除风险，复杂性可能放大传染效应',
    'system',
    0.95
);

-- 加密货币监管
INSERT INTO event_representations (event_id, surface_summary, surface_entities, surface_numbers, causal_pattern, causal_pattern_desc, decision_logic, transmission_mechanism, constraint_conditions, economic_principle, economic_principle_desc, ai_model, ai_confidence) VALUES
(
    'hist_crypto_crackdown_2023',
    '全球加密货币监管收紧，行业走向合规化',
    '["SEC", "币安", "Coinbase", "FTX", "MiCA"]'::jsonb,
    '{"market_cap_decline_pct": -65, "exchange_bankruptcies": 3}'::jsonb,
    'regulatory_crackdown_industry_adjust',
    'FTX倒闭暴露行业乱象，各国加速出台监管框架，加密行业从野蛮生长转向合规化发展',
    '监管机构选择收紧是因为行业风险外溢（投资者损失、洗钱风险），需要建立规则保护投资者',
    '行业丑闻→监管关注→执法行动→行业洗牌→合规成本上升→投机资金退出→机构资金入场',
    '["投资者保护", "金融稳定", "反洗钱"]'::jsonb,
    'regulatory_crackdown_industry_adjust',
    '新兴行业往往经历"创新-泡沫-危机-监管"循环，合规化是行业成熟的必经之路',
    'system',
    0.95
);
