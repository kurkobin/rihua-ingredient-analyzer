"""成分匹配服务

从 OCR 识别的文字中匹配成分,并返回已知成分的风险信息。
MVP 阶段使用内存字典,后续迁移到 SQLite。
"""
import re

from app.models.schemas import IngredientInfo


# 日化洗护核心成分库(100+种,覆盖牙膏/洗发水/沐浴露/护肤品)
# 字段:分类 / 风险等级 / 说明
INGREDIENT_DB: dict[str, dict[str, str]] = {
    # ===== 表面活性剂(15种) =====
    "月桂醇硫酸酯钠": {
        "category": "表面活性剂",
        "risk_level": "慎用",
        "description": "即 SLS/K12,清洁力极强,刺激性较大,可能引起皮肤干燥、敏感,口腔黏膜可能受刺激",
        "reference": "CIR 评估认为安全",
    },
    "月桂醇聚醚硫酸酯钠": {
        "category": "表面活性剂",
        "risk_level": "注意",
        "description": "即 SLES,清洁力强,生产过程可能残留二恶烷(致癌物),正规产品已控制残留",
        "reference": "CIR 评估认为安全",
    },
    "椰油酰胺丙基甜菜碱": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "温和两性表活,常与 SLES 复配以降低刺激性",
        "reference": "CIR 评估认为安全",
    },
    "月桂酰肌氨酸钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "氨基酸表活,温和低刺激",
        "reference": "CIR 评估认为安全",
    },
    "椰油酰谷氨酸钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "氨基酸表活,温和亲肤",
        "reference": "CIR 评估认为安全",
    },
    "月桂酰谷氨酸钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "氨基酸表活,温和清洁",
        "reference": "CIR 评估认为安全",
    },
    "椰油酰甘氨酸钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "氨基酸表活,温和亲肤",
        "reference": "CIR 评估认为安全",
    },
    "月桂酰羟甲基牛磺酸钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "温和氨基酸表活,适合敏感肌",
        "reference": "暂无明确法规依据",
    },
    "烷基糖苷": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "APG,植物来源温和表活,可降解",
        "reference": "CIR 评估认为安全",
    },
    "椰油酰胺MEA": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "增泡剂和增稠剂,辅助表活",
        "reference": "CIR 评估认为安全",
    },
    "椰油酰胺DEA": {
        "category": "表面活性剂",
        "risk_level": "注意",
        "description": "增泡增稠剂,可能产生亚硝胺杂质",
        "reference": "CIR 评估认为安全",
    },
    "十二烷基苯磺酸钠": {
        "category": "表面活性剂",
        "risk_level": "注意",
        "description": "LAS,清洁力强但刺激性较大,多用于洗衣液",
        "reference": "暂无明确法规依据",
    },
    "硬脂酸钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "皂基,用于固体清洁产品",
        "reference": "常用成分，未见安全风险报告",
    },
    "棕榈酰谷氨酸钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "温和氨基酸表活",
        "reference": "暂无明确法规依据",
    },
    "PEG-40 氢化蓖麻油": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "乳化剂和增溶剂,用于香精溶解",
        "reference": "CIR 评估认为安全",
    },

    # ===== 防龋/口腔护理成分(8种) =====
    "氟化钠": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "预防蛀牙的有效成分,适量使用安全",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的防龋成分",
    },
    "单氟磷酸钠": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "预防蛀牙,常见于含氟牙膏",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的防龋成分",
    },
    "氟化亚锡": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "防龋兼抗菌,可能引起轻微牙齿染色",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的防龋成分",
    },
    "木糖醇": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "天然甜味剂,抑制致龋菌",
        "reference": "常用成分，未见安全风险报告",
    },
    "山梨醇": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "保湿兼甜味剂,温和",
        "reference": "常用成分，未见安全风险报告",
    },
    "氯己定": {
        "category": "抗菌剂",
        "risk_level": "注意",
        "description": "强效抗菌,长期使用可能导致牙齿染色",
        "reference": "暂无明确法规依据",
    },
    "西吡氯铵": {
        "category": "抗菌剂",
        "risk_level": "安全",
        "description": "抗菌成分,减少牙菌斑",
        "reference": "暂无明确法规依据",
    },
    "羟基磷灰石": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "仿生修复牙釉质,温和有效",
        "reference": "暂无明确法规依据",
    },

    # ===== 防腐剂(12种) =====
    "对羟基苯甲酸甲酯": {
        "category": "防腐剂",
        "risk_level": "慎用",
        "description": "尼泊金酯类防腐剂,有内分泌干扰争议",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，单一酯最大允许浓度0.4%，混合酯总量0.8%",
    },
    "对羟基苯甲酸乙酯": {
        "category": "防腐剂",
        "risk_level": "慎用",
        "description": "尼泊金酯类防腐剂,有争议",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，单一酯最大允许浓度0.4%，混合酯总量0.8%",
    },
    "对羟基苯甲酸丙酯": {
        "category": "防腐剂",
        "risk_level": "慎用",
        "description": "尼泊金丙酯,争议较大,部分国家限制使用",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，单一酯最大允许浓度0.4%，混合酯总量0.8%；欧盟 (EU) No 358/2014 禁用于3岁以下儿童驻留类产品",
    },
    "对羟基苯甲酸丁酯": {
        "category": "防腐剂",
        "risk_level": "慎用",
        "description": "尼泊金丁酯,争议最大的尼泊金酯类",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，单一酯最大允许浓度0.4%，混合酯总量0.8%；欧盟 (EU) No 358/2014 禁用于3岁以下儿童驻留类产品",
    },
    "甲基异噻唑啉酮": {
        "category": "防腐剂",
        "risk_level": "规避",
        "description": "MIT,高致敏性,驻留类化妆品已禁用",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，最大允许浓度0.01%；欧盟 (EC) No 1004/2014 禁用于驻留类化妆品",
    },
    "甲基氯异噻唑啉酮": {
        "category": "防腐剂",
        "risk_level": "规避",
        "description": "CMIT,与MIT复配使用,高致敏性",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，仅允许与MIT复配用于淋洗类化妆品，最大允许浓度0.0015%",
    },
    "苯氧乙醇": {
        "category": "防腐剂",
        "risk_level": "安全",
        "description": "常用防腐剂,安全性较好",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，最大允许浓度1.0%",
    },
    "苯甲醇": {
        "category": "防腐剂",
        "risk_level": "注意",
        "description": "防腐兼溶剂,部分人群过敏",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂",
    },
    "苯甲酸钠": {
        "category": "防腐剂",
        "risk_level": "安全",
        "description": "常用食品级防腐剂,安全性好",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂（以苯甲酸计），最大允许浓度0.5%",
    },
    "山梨酸钾": {
        "category": "防腐剂",
        "risk_level": "安全",
        "description": "食品级防腐剂,温和安全",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂（以山梨酸计）",
    },
    "脱氢乙酸": {
        "category": "防腐剂",
        "risk_level": "注意",
        "description": "防腐剂,部分国家限制在化妆品中使用",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，最大允许浓度0.6%",
    },
    "咪唑烷基脲": {
        "category": "防腐剂",
        "risk_level": "注意",
        "description": "甲醛释放型防腐剂,可能释放微量甲醛",
        "reference": "暂无明确法规依据",
    },

    # ===== 保湿剂(10种) =====
    "甘油": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "经典保湿剂,温和",
        "reference": "常用成分，未见安全风险报告",
    },
    "透明质酸钠": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "玻尿酸,强效保湿",
        "reference": "常用成分，未见安全风险报告",
    },
    "丙二醇": {
        "category": "保湿剂",
        "risk_level": "注意",
        "description": "保湿兼促渗,高浓度可能刺激",
        "reference": "CIR 评估认为安全",
    },
    "丁二醇": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "温和保湿剂",
        "reference": "常用成分，未见安全风险报告",
    },
    "泛醇": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "维生素B5,保湿修护,温和亲肤",
        "reference": "CIR 评估认为安全",
    },
    "尿囊素": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "舒缓和促进修复,温和",
        "reference": "CIR 评估认为安全",
    },
    "吡咯烷酮羧酸钠": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "PCA-Na,天然保湿因子成分",
        "reference": "CIR 评估认为安全",
    },
    "乳酸钠": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "天然保湿因子,调节皮肤pH",
        "reference": "CIR 评估认为安全",
    },
    "双丙甘醇": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "温和保湿溶剂",
        "reference": "CIR 评估认为安全",
    },
    "聚乙二醇-8": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "PEG-8,保湿兼溶剂",
        "reference": "CIR 评估认为安全",
    },

    # ===== 溶剂/基质(6种) =====
    "水": {
        "category": "溶剂",
        "risk_level": "安全",
        "description": "溶剂",
        "reference": "常用成分，未见安全风险报告",
    },
    "变性乙醇": {
        "category": "溶剂",
        "risk_level": "注意",
        "description": "酒精,溶解性好但可能干燥刺激",
        "reference": "常用成分，未见安全风险报告",
    },
    "乙醇": {
        "category": "溶剂",
        "risk_level": "注意",
        "description": "酒精,溶剂和防腐辅助,高浓度可能干燥刺激",
        "reference": "常用成分，未见安全风险报告",
    },
    "异丙醇": {
        "category": "溶剂",
        "risk_level": "注意",
        "description": "溶剂,有挥发性,刺激性较强",
        "reference": "暂无明确法规依据",
    },
    "1,3-丙二醇": {
        "category": "溶剂",
        "risk_level": "安全",
        "description": "天然来源溶剂,温和",
        "reference": "CIR 评估认为安全",
    },
    "碳酸氢钠": {
        "category": "溶剂",
        "risk_level": "安全",
        "description": "小苏打,调节pH,牙膏中常见",
        "reference": "常用成分，未见安全风险报告",
    },

    # ===== 增稠/稳定剂(8种) =====
    "卡波姆": {
        "category": "增稠剂",
        "risk_level": "安全",
        "description": "常用增稠稳定剂",
        "reference": "CIR 评估认为安全",
    },
    "黄原胶": {
        "category": "增稠剂",
        "risk_level": "安全",
        "description": "天然增稠剂",
        "reference": "常用成分，未见安全风险报告",
    },
    "羟乙基纤维素": {
        "category": "增稠剂",
        "risk_level": "安全",
        "description": "增稠剂",
        "reference": "CIR 评估认为安全",
    },
    "羧甲基纤维素钠": {
        "category": "增稠剂",
        "risk_level": "安全",
        "description": "CMC,增稠和粘合剂,食品级安全",
        "reference": "常用成分，未见安全风险报告",
    },
    "微晶纤维素": {
        "category": "增稠剂",
        "risk_level": "安全",
        "description": "研磨和增稠辅助,温和",
        "reference": "常用成分，未见安全风险报告",
    },
    "瓜尔胶": {
        "category": "增稠剂",
        "risk_level": "安全",
        "description": "天然植物胶,洗发水调理剂",
        "reference": "常用成分，未见安全风险报告",
    },
    "丙烯酸酯共聚物": {
        "category": "增稠剂",
        "risk_level": "安全",
        "description": "增稠和成膜剂",
        "reference": "CIR 评估认为安全",
    },
    "纤维素胶": {
        "category": "增稠剂",
        "risk_level": "安全",
        "description": "天然增稠剂,温和安全",
        "reference": "常用成分，未见安全风险报告",
    },

    # ===== 香精/色素(8种) =====
    "香精": {
        "category": "香精",
        "risk_level": "注意",
        "description": "致敏源之一,敏感肌注意",
        "reference": "国际日用香料香精协会 (IFRA) 标准",
    },
    "CI 19140": {
        "category": "色素",
        "risk_level": "安全",
        "description": "黄色色素",
        "reference": "《化妆品安全技术规范》(2015版) 准用色素列表",
    },
    "CI 42090": {
        "category": "色素",
        "risk_level": "安全",
        "description": "蓝色色素",
        "reference": "《化妆品安全技术规范》(2015版) 准用色素列表",
    },
    "CI 16035": {
        "category": "色素",
        "risk_level": "安全",
        "description": "红色色素",
        "reference": "《化妆品安全技术规范》(2015版) 准用色素列表",
    },
    "CI 14700": {
        "category": "色素",
        "risk_level": "安全",
        "description": "红色4号色素",
        "reference": "《化妆品安全技术规范》(2015版) 准用色素列表",
    },
    "CI 47005": {
        "category": "色素",
        "risk_level": "安全",
        "description": "黄色10号色素",
        "reference": "《化妆品安全技术规范》(2015版) 准用色素列表",
    },
    "薄荷醇": {
        "category": "香精",
        "risk_level": "安全",
        "description": "清凉剂,提供清新感,温和",
        "reference": "常用成分，未见安全风险报告",
    },
    "薄荷油": {
        "category": "香精",
        "risk_level": "安全",
        "description": "天然薄荷精油,提供清凉感",
        "reference": "暂无明确法规依据",
    },

    # ===== 活性成分-护肤(15种) =====
    "烟酰胺": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "美白提亮,低浓度温和,建立耐受后使用",
        "reference": "CIR 评估认为安全",
    },
    "视黄醇": {
        "category": "活性成分",
        "risk_level": "注意",
        "description": "维生素A衍生物,抗老有效但孕妇慎用,可能刺激",
        "reference": "CIR 评估认为安全",
    },
    "抗坏血酸": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "维生素C,抗氧化美白",
        "reference": "CIR 评估认为安全",
    },
    "神经酰胺": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "修复屏障",
        "reference": "暂无明确法规依据",
    },
    "维生素E": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "抗氧化,保湿修护",
        "reference": "CIR 评估认为安全",
    },
    "生育酚乙酸酯": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "维生素E衍生物,抗氧化稳定",
        "reference": "CIR 评估认为安全",
    },
    "熊果苷": {
        "category": "活性成分",
        "risk_level": "注意",
        "description": "美白成分,高浓度可能刺激,需注意用量",
        "reference": "暂无明确法规依据",
    },
    "光果甘草根提取物": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "美白抗氧化,温和",
        "reference": "暂无明确法规依据",
    },
    "积雪草提取物": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "舒缓修复,促进伤口愈合",
        "reference": "暂无明确法规依据",
    },
    "芦荟提取物": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "舒缓保湿,温和",
        "reference": "CIR 评估认为安全",
    },
    "茶树油": {
        "category": "活性成分",
        "risk_level": "注意",
        "description": "抗菌控油,高浓度可能刺激",
        "reference": "暂无明确法规依据",
    },
    "水杨酸": {
        "category": "活性成分",
        "risk_level": "注意",
        "description": "去角质控油,孕妇慎用,敏感肌注意",
        "reference": "《化妆品安全技术规范》(2015版) 限用成分，驻留类最大允许浓度2.0%（3岁以下儿童不得使用）",
    },
    "果酸": {
        "category": "活性成分",
        "risk_level": "注意",
        "description": "去角质促进更新,高浓度可能刺激,需防晒",
        "reference": "《化妆品安全技术规范》(2015版) 限用成分（α-羟基酸）",
    },
    "甘醇酸": {
        "category": "活性成分",
        "risk_level": "注意",
        "description": "小分子果酸,渗透快,可能刺激",
        "reference": "《化妆品安全技术规范》(2015版) 限用成分（α-羟基酸）",
    },
    "辅酶Q10": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "抗氧化抗衰老,温和",
        "reference": "暂无明确法规依据",
    },

    # ===== 研磨剂(牙膏)(5种) =====
    "水合硅石": {
        "category": "研磨剂",
        "risk_level": "安全",
        "description": "二氧化硅,常用研磨剂",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "碳酸钙": {
        "category": "研磨剂",
        "risk_level": "安全",
        "description": "常用研磨剂",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "磷酸氢钙": {
        "category": "研磨剂",
        "risk_level": "安全",
        "description": "温和研磨剂,高级牙膏常用",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "氧化铝": {
        "category": "研磨剂",
        "risk_level": "安全",
        "description": "研磨剂,用于美白牙膏",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "焦磷酸钙": {
        "category": "研磨剂",
        "risk_level": "安全",
        "description": "研磨兼防牙石",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },

    # ===== 硅油/顺滑剂(4种) =====
    "聚二甲基硅氧烷": {
        "category": "硅油",
        "risk_level": "安全",
        "description": "硅油,顺滑剂,难降解但安全",
        "reference": "CIR 评估认为安全",
    },
    "环五聚二甲基硅氧烷": {
        "category": "硅油",
        "risk_level": "注意",
        "description": "D5,挥发性硅油,难降解,部分国家限制",
        "reference": "欧盟 (EU) 2018/2005 限制用于化妆品（淋洗类限0.1%，驻留类禁用）",
    },
    "环己硅氧烷": {
        "category": "硅油",
        "risk_level": "安全",
        "description": "挥发性硅油,提供清爽感",
        "reference": "暂无明确法规依据",
    },
    "氨端聚二甲基硅氧烷": {
        "category": "硅油",
        "risk_level": "安全",
        "description": "氨基改性硅油,护发调理",
        "reference": "CIR 评估认为安全",
    },

    # ===== 螯合剂/缓冲剂(5种) =====
    "EDTA二钠": {
        "category": "螯合剂",
        "risk_level": "安全",
        "description": "螯合剂,稳定配方",
        "reference": "CIR 评估认为安全",
    },
    "EDTA四钠": {
        "category": "螯合剂",
        "risk_level": "安全",
        "description": "螯合剂,稳定配方",
        "reference": "CIR 评估认为安全",
    },
    "柠檬酸": {
        "category": "缓冲剂",
        "risk_level": "安全",
        "description": "pH调节剂,温和",
        "reference": "常用成分，未见安全风险报告",
    },
    "柠檬酸钠": {
        "category": "缓冲剂",
        "risk_level": "安全",
        "description": "pH调节缓冲剂",
        "reference": "常用成分，未见安全风险报告",
    },
    "磷酸氢二钠": {
        "category": "缓冲剂",
        "risk_level": "安全",
        "description": "pH缓冲剂",
        "reference": "常用成分，未见安全风险报告",
    },

    # ===== 抗菌剂/去屑剂(6种) =====
    "三氯生": {
        "category": "抗菌剂",
        "risk_level": "规避",
        "description": "抗菌剂,有内分泌干扰争议,部分国家已禁用",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，最大允许浓度0.3%；FDA 2016年禁用于抗菌洗护产品",
    },
    "吡硫鎓锌": {
        "category": "去屑剂",
        "risk_level": "注意",
        "description": "ZPT,去屑有效,但部分国家已限制使用",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂；欧盟 (EU) 2022/660 禁用于化妆品",
    },
    "吡罗克酮乙醇胺盐": {
        "category": "去屑剂",
        "risk_level": "安全",
        "description": "OCT,温和有效去屑",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂",
    },
    "酮康唑": {
        "category": "去屑剂",
        "risk_level": "注意",
        "description": "药用去屑成分,需遵医嘱",
        "reference": "暂无明确法规依据",
    },
    "水杨酸钠": {
        "category": "抗菌剂",
        "risk_level": "注意",
        "description": "抗菌角质软化,高浓度可能刺激",
        "reference": "暂无明确法规依据",
    },
    "三氯卡班": {
        "category": "抗菌剂",
        "risk_level": "规避",
        "description": "抗菌剂,有安全性争议,美国已禁用于洗护产品",
        "reference": "FDA 2016年禁用于抗菌洗护产品",
    },

    # ===== 油脂/乳化剂(10种) =====
    "矿油": {
        "category": "油脂",
        "risk_level": "注意",
        "description": "矿物油,封闭性好但可能致痘,纯度要求高",
        "reference": "CIR 评估认为安全",
    },
    "矿脂": {
        "category": "油脂",
        "risk_level": "注意",
        "description": "凡士林,封闭性极强,可能致痘",
        "reference": "CIR 评估认为安全",
    },
    "角鲨烷": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "亲肤油脂,保湿滋润",
        "reference": "常用成分，未见安全风险报告",
    },
    "霍霍巴油": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "植物油,亲肤保湿",
        "reference": "CIR 评估认为安全",
    },
    "乳木果油": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "天然油脂,深层滋润",
        "reference": "暂无明确法规依据",
    },
    "甘油硬脂酸酯": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "常用乳化剂",
        "reference": "CIR 评估认为安全",
    },
    "PEG-100 硬脂酸酯": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "乳化剂,常见于乳液面霜",
        "reference": "CIR 评估认为安全",
    },
    "鲸蜡硬脂醇": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "脂肪醇,增稠和乳化稳定",
        "reference": "CIR 评估认为安全",
    },
    "硬脂酸": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "脂肪酸,皂化基质",
        "reference": "常用成分，未见安全风险报告",
    },
    "聚山梨醇酯-20": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "吐温20,乳化增溶剂",
        "reference": "CIR 评估认为安全",
    },

    # ===== 其他功效/添加剂(8种) =====
    "糖精钠": {
        "category": "甜味剂",
        "risk_level": "安全",
        "description": "人工甜味剂,牙膏中提供甜味",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "氯化钠": {
        "category": "调节剂",
        "risk_level": "安全",
        "description": "食盐,调节粘度和电解质",
        "reference": "常用成分，未见安全风险报告",
    },
    "氯化锶": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "抗敏感成分,缓解牙齿敏感",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "硝酸钾": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "抗敏感成分,舒缓牙神经",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "精氨酸": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "氨基酸,抗敏修复",
        "reference": "CIR 评估认为安全",
    },
    "葡聚糖": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "β-葡聚糖,舒缓修护增强免疫",
        "reference": "暂无明确法规依据",
    },
    "二肽-2": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "多肽成分,抗皱紧致",
        "reference": "暂无明确法规依据",
    },
    "棕榈酰五肽-4": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "多肽,促进胶原蛋白生成",
        "reference": "暂无明确法规依据",
    },
}


# 同义词归一(俗称/英文名 -> 标准名)
SYNONYMS: dict[str, str] = {
    # 表面活性剂
    "SLS": "月桂醇硫酸酯钠",
    "K12": "月桂醇硫酸酯钠",
    "sodium lauryl sulfate": "月桂醇硫酸酯钠",
    "sodium dodecyl sulfate": "月桂醇硫酸酯钠",
    "十二烷基硫酸钠": "月桂醇硫酸酯钠",
    "SLES": "月桂醇聚醚硫酸酯钠",
    "sodium laureth sulfate": "月桂醇聚醚硫酸酯钠",
    "CAB": "椰油酰胺丙基甜菜碱",
    "LAB": "月桂酰胺丙基甜菜碱",
    "APG": "烷基糖苷",
    "LAS": "十二烷基苯磺酸钠",
    # 尼泊金酯类
    "尼泊金甲酯": "对羟基苯甲酸甲酯",
    "尼泊金乙酯": "对羟基苯甲酸乙酯",
    "尼泊金丙酯": "对羟基苯甲酸丙酯",
    "尼泊金丁酯": "对羟基苯甲酸丁酯",
    "羟苯甲酯": "对羟基苯甲酸甲酯",
    "羟苯乙酯": "对羟基苯甲酸乙酯",
    "羟苯丙酯": "对羟基苯甲酸丙酯",
    "羟苯丁酯": "对羟基苯甲酸丁酯",
    "methylparaben": "对羟基苯甲酸甲酯",
    "ethylparaben": "对羟基苯甲酸乙酯",
    "propylparaben": "对羟基苯甲酸丙酯",
    "butylparaben": "对羟基苯甲酸丁酯",
    # 防腐剂缩写
    "MIT": "甲基异噻唑啉酮",
    "CMIT": "甲基氯异噻唑啉酮",
    "甲基异噻唑啉酮": "甲基异噻唑啉酮",
    # 保湿剂
    "玻尿酸": "透明质酸钠",
    "透明质酸": "透明质酸钠",
    "hyaluronic acid": "透明质酸钠",
    "维生素b5": "泛醇",
    "泛酰醇": "泛醇",
    "panthenol": "泛醇",
    "尿膜素": "尿囊素",
    # 维生素类
    "维生素c": "抗坏血酸",
    "vc": "抗坏血酸",
    "vitamin c": "抗坏血酸",
    "维生素a": "视黄醇",
    "a醇": "视黄醇",
    "retinol": "视黄醇",
    "维生素e": "生育酚乙酸酯",
    "ve": "生育酚乙酸酯",
    "vitamin e": "生育酚乙酸酯",
    "生育酚": "维生素E",
    # 硅油
    "硅油": "聚二甲基硅氧烷",
    "dimethicone": "聚二甲基硅氧烷",
    "聚二甲基硅氧烷": "聚二甲基硅氧烷",
    "环五硅氧烷": "环五聚二甲基硅氧烷",
    "D5": "环五聚二甲基硅氧烷",
    # 去屑剂
    "ZPT": "吡硫鎓锌",
    "吡啶硫酮锌": "吡硫鎓锌",
    "zinc pyrithione": "吡硫鎓锌",
    "OCT": "吡罗克酮乙醇胺盐",
    "吡罗克酮乙醇胺盐": "吡罗克酮乙醇胺盐",
    # 油脂
    "凡士林": "矿脂",
    "petrolatum": "矿脂",
    "白油": "矿油",
    "液体石蜡": "矿油",
    "mineral oil": "矿油",
    # 其他
    "水杨酸": "水杨酸",
    "salicylic acid": "水杨酸",
    "果酸": "果酸",
    "aha": "果酸",
    "辅酶": "辅酶Q10",
    "coenzyme q10": "辅酶Q10",
    "泛醌": "辅酶Q10",
    "小苏打": "碳酸氢钠",
    "baking soda": "碳酸氢钠",
    "食盐": "氯化钠",
    "吐温20": "聚山梨醇酯-20",
    "tween 20": "聚山梨醇酯-20",
    "十六十八醇": "鲸蜡硬脂醇",
    "cetearyl alcohol": "鲸蜡硬脂醇",
    "神经酰胺": "神经酰胺",
    "ceramide": "神经酰胺",
    "角鲨烯": "角鲨烷",
    "squalane": "角鲨烷",
    # 香精
    "(日用)香精": "香精",
    "日用香精": "香精",
    "日用了香精": "香精",
}


class IngredientService:
    """成分匹配服务"""

    # 非成分文本的关键词(出现这些词的行不是成分)
    NOISE_KEYWORDS = [
        "使用方法", "注意", "保存方法", "贮存方法", "贮存条件",
        "生产许可证", "卫生许可证", "执行标准", "产品标准",
        "生产企业", "委托方", "受托方", "地址", "产地",
        "净含量", "生产日期", "保质期", "批号",
        "请于", "避免阳光", "常温保存", "阴凉处",
        "儿童应当", "成人监护", "若不慎", "请立即",
        "停止使用", "暂停使用", "不适", "请暂",
        "用水清洗", "皮肤不适", "按摩", "涂抹于",
        "取适量", "揉搓", "用清水冲净",
        "指", "指水", "指双", "指母", "指椰",
        "儿童", "婴幼儿", "适用于",
    ]

    # 成分列表前缀(需要清除,支持多行匹配)
    PREFIX_PATTERNS = [
        r"(?m)^成分[:：]\s*",
        r"(?m)^配料[:：]\s*",
        r"(?m)^配料表[:：]\s*",
        r"(?m)^其他微量成分[:：]\s*",
        r"(?m)^微量成分[:：]\s*",
        r"(?m)^全成分[:：]\s*",
        r"(?m)^Ingredients?[:：]\s*",
    ]

    def __init__(self):
        self.db = INGREDIENT_DB
        self.synonyms = SYNONYMS

    def match_ingredients(self, text: str) -> list[IngredientInfo]:
        """从 OCR 文本中匹配成分

        Args:
            text: OCR 识别的配料表原文

        Returns:
            匹配到的成分列表(保留原始顺序,去重)
        """
        # 1. 清除前缀("成分："、"配料表："等)
        cleaned = text
        for pattern in self.PREFIX_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned)

        # 2. 合并被换行截断的行
        # OCR 经常在成分中间换行,如"癸\n基葡糖苷"应合并为"癸基葡糖苷"
        # 策略:如果一行不以分隔符结尾,且下一行不以分隔符开头,则合并
        lines = cleaned.split("\n")
        merged_lines: list[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if merged_lines:
                prev = merged_lines[-1]
                # 如果上一行以分隔符结尾,或是噪音行,则不合并
                prev_ends_sep = re.search(r"[,，、;；]$", prev)
                curr_starts_sep = re.match(r"^[,，、;；]", line)
                is_prev_noise = any(kw in prev for kw in self.NOISE_KEYWORDS)
                is_curr_noise = any(kw in line for kw in self.NOISE_KEYWORDS)
                # 如果上一行不以分隔符结尾,且当前行不以分隔符开头,且都不是噪音行
                # 则可能是换行截断,尝试合并
                if not prev_ends_sep and not curr_starts_sep and not is_prev_noise and not is_curr_noise:
                    merged_lines[-1] = prev + line
                    continue
            merged_lines.append(line)

        # 3. 重新按分隔符拆分
        raw_text = "\n".join(merged_lines)
        raw_items = re.split(r"[,，、;；\n]+", raw_text)

        # 4. 过滤和匹配
        results: list[IngredientInfo] = []
        seen: set[str] = set()

        for item in raw_items:
            item = item.strip()

            # 过滤过短或过长的项
            if not item or len(item) < 2 or len(item) > 50:
                continue

            # 过滤噪音文本(使用方法、注意等)
            if any(kw in item for kw in self.NOISE_KEYWORDS):
                continue

            # 过滤纯数字、纯标点
            if re.match(r"^[\d\s\.\-]+$", item):
                continue

            # 过滤包含句号、感叹号等非成分标点的项
            # 成分名称不会以句号结尾
            if re.search(r"[。！？]$", item):
                continue

            # 同义词归一(不删除括号,保留原始成分名)
            normalized = self._normalize(item)
            if normalized in seen:
                continue
            seen.add(normalized)

            info = self.db.get(normalized)
            if info:
                results.append(IngredientInfo(
                    name=normalized,
                    category=info["category"],
                    risk_level=info["risk_level"],
                    description=info["description"],
                    in_database=True,
                    reference=info.get("reference", ""),
                ))
            else:
                # 未在库中,仍记录(LLM 兜底分析)
                results.append(IngredientInfo(
                    name=item,
                    in_database=False,
                    reference="LLM 分析,未经数据库核实",
                ))

        return results

    def _normalize(self, name: str) -> str:
        """成分名称归一:同义词转标准名"""
        # 精确匹配同义词
        if name in self.synonyms:
            return self.synonyms[name]
        # 大小写不敏感匹配英文名
        lower = name.lower()
        if lower in self.synonyms:
            return self.synonyms[lower]
        return name
