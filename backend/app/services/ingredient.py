"""成分匹配服务

从 OCR 识别的文字中匹配成分,并返回已知成分的风险信息。
成分数据存储在 SQLite 数据库(由 seed.py 导入),本模块只负责匹配逻辑。
"""
import re

from app.database import find_ingredient
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

    # ===== 防晒剂(15种) =====
    "丁基甲氧基二苯甲酰甲烷": {
        "category": "防晒剂",
        "risk_level": "注意",
        "description": "即阿伏苯宗,常用 UVA 防晒剂,光稳定性差需复配",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 5%",
    },
    "甲氧基肉桂酸乙基己酯": {
        "category": "防晒剂",
        "risk_level": "注意",
        "description": "即桂皮酸盐,主流 UVB 防晒剂,有潜在内分泌干扰争议",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 10%",
    },
    "奥克立林": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "UVB 防晒剂,光稳定性好,常作助防晒",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 10%",
    },
    "二苯酮-3": {
        "category": "防晒剂",
        "risk_level": "慎用",
        "description": "UVA/UVB 防晒剂,致敏率较高,有争议",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 10%，产品需标注“含二苯酮-3”",
    },
    "二苯酮-4": {
        "category": "防晒剂",
        "risk_level": "注意",
        "description": "UVA 防晒剂,致敏风险较二苯酮-3 低",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 5%",
    },
    "水杨酸乙基己酯": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "即水杨酸辛酯,UVB 防晒剂,温和",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 5%",
    },
    "胡莫柳酯": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "即水杨酸三甲环己酯,UVB 防晒剂",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 10%",
    },
    "乙基己基三嗪酮": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "UVB 防晒剂,光稳定性强,防护效率高",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 5%",
    },
    "双-乙基己氧苯酚甲氧苯基三嗪": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "即 Tinosorb S,广谱防晒剂,UVA/UVB 双防护",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 10%",
    },
    "亚甲基双-苯并三唑基四甲基丁基酚": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "即 Tinosorb M,广谱物理-化学防晒剂",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 10%",
    },
    "苯基苯并咪唑磺酸": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "UVB 防晒剂,水溶性,常用于防晒乳液",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 8%",
    },
    "对氨基苯甲酸": {
        "category": "防晒剂",
        "risk_level": "慎用",
        "description": "PABA,早期 UVB 防晒剂,致敏率高,已较少使用",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 5%",
    },
    "二氧化钛": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "物理防晒剂,广谱防护,温和低刺激,敏感肌可用",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂",
    },
    "氧化锌": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "物理防晒剂,广谱防护,舒缓收敛",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂",
    },
    "聚硅氧烷-15": {
        "category": "防晒剂",
        "risk_level": "安全",
        "description": "即 Parsol SLX,UVB 防晒剂,兼护发",
        "reference": "《化妆品安全技术规范》(2015版) 准用防晒剂，最大允许浓度 10%",
    },

    # ===== 染发剂(10种) =====
    "对苯二胺": {
        "category": "染发剂",
        "risk_level": "慎用",
        "description": "即 PPD,永久性染发剂主中间体,强致敏,严重过敏反应风险",
        "reference": "《化妆品安全技术规范》(2015版) 限用染发剂，最大允许浓度 2%（一般染发产品）/ 6%（专业染发产品）",
    },
    "对氨基苯酚": {
        "category": "染发剂",
        "risk_level": "注意",
        "description": "染发剂中间体,致敏性较 PPD 低",
        "reference": "《化妆品安全技术规范》(2015版) 限用染发剂，最大允许浓度 1%",
    },
    "间氨基苯酚": {
        "category": "染发剂",
        "risk_level": "注意",
        "description": "染发剂偶联剂,常与 PPD 复配",
        "reference": "《化妆品安全技术规范》(2015版) 限用染发剂，最大允许浓度 2%",
    },
    "对甲苯二胺": {
        "category": "染发剂",
        "risk_level": "注意",
        "description": "即 PTD,PPD 替代品,致敏性略低",
        "reference": "《化妆品安全技术规范》(2015版) 限用染发剂，最大允许浓度 4%（一般）/ 10%（专业）",
    },
    "间苯二酚": {
        "category": "染发剂",
        "risk_level": "注意",
        "description": "染发偶联剂,兼防腐,甲状腺干扰争议",
        "reference": "《化妆品安全技术规范》(2015版) 限用染发剂，最大允许浓度 0.5%（一般染发）/ 5%（专业染发）",
    },
    "4-氨基-2-羟基甲苯": {
        "category": "染发剂",
        "risk_level": "注意",
        "description": "染发剂中间体,常用于棕黑色调",
        "reference": "《化妆品安全技术规范》(2015版) 限用染发剂，最大允许浓度 3%",
    },
    "2,4-二氨基苯氧基乙醇盐酸盐": {
        "category": "染发剂",
        "risk_level": "注意",
        "description": "染发剂中间体,PPD 替代成分",
        "reference": "《化妆品安全技术规范》(2015版) 限用染发剂，最大允许浓度 2%",
    },
    "苯基甲基吡唑啉酮": {
        "category": "染发剂",
        "risk_level": "注意",
        "description": "染发剂偶联剂,常用于染色调节",
        "reference": "《化妆品安全技术规范》(2015版) 限用染发剂，最大允许浓度 2%",
    },
    "硝酸镁": {
        "category": "染发剂",
        "risk_level": "安全",
        "description": "染发剂稳定剂,调节颜色持久度",
        "reference": "《化妆品安全技术规范》(2015版) 染发剂着色剂组分",
    },
    "硫酸亚铁": {
        "category": "染发剂",
        "risk_level": "安全",
        "description": "金属盐染发剂,植物染发体系辅助剂",
        "reference": "常用成分，未见安全风险报告",
    },

    # ===== 去屑剂(8种) =====
    "吡硫鎓锌": {
        "category": "去屑剂",
        "risk_level": "注意",
        "description": "即 ZPT,传统去屑剂,环境毒性争议,欧盟已禁用于化妆品",
        "reference": "《化妆品安全技术规范》(2015版) 准用去屑剂，最大允许浓度 1.5%；欧盟 (EU) 2022/631 已禁用",
    },
    "酮康唑": {
        "category": "去屑剂",
        "risk_level": "慎用",
        "description": "处方级抗真菌去屑成分,属于药物,化妆品中禁用",
        "reference": "《化妆品安全技术规范》(2015版) 化妆品禁用成分（药物成分）",
    },
    "二硫化硒": {
        "category": "去屑剂",
        "risk_level": "慎用",
        "description": "非处方去屑剂,有药物属性,可能引起头皮刺激",
        "reference": "国家非处方药目录,化妆品中限用",
    },
    "吡罗克酮乙醇胺盐": {
        "category": "去屑剂",
        "risk_level": "安全",
        "description": "即 OCT,温和高效去屑剂,致敏性低",
        "reference": "《化妆品安全技术规范》(2015版) 准用去屑剂，最大允许浓度 1%",
    },
    "氯咪巴唑": {
        "category": "去屑剂",
        "risk_level": "安全",
        "description": "即甘宝素,去屑抗真菌,温和",
        "reference": "《化妆品安全技术规范》(2015版) 准用去屑剂，最大允许浓度 0.5%",
    },
    "环吡酮胺": {
        "category": "去屑剂",
        "risk_level": "注意",
        "description": "抗真菌成分,多用于药物,化妆品限用",
        "reference": "国家非处方药目录",
    },
    "水杨酸": {
        "category": "去屑剂",
        "risk_level": "注意",
        "description": "角质剥脱剂,辅助去屑去痘,浓度相关刺激性",
        "reference": "《化妆品安全技术规范》(2015版) 限用成分，淋洗类最大 2%，驻留类最大 2%",
    },
    "煤焦油": {
        "category": "去屑剂",
        "risk_level": "慎用",
        "description": "传统去屑剂,含多环芳烃,有致癌风险,已少用",
        "reference": "《化妆品安全技术规范》(2015版) 限用去屑剂，淋洗类洗发水最大 1%",
    },

    # ===== 美白活性成分(17种) =====
    "3-邻-乙基抗坏血酸": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "即 EAE,维 C 衍生物,稳定性好,美白提亮",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "抗坏血酸葡糖苷": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "即 AA2G,维 C 衍生物,温和美白",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "抗坏血酸磷酸酯镁": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "即 MAP,维 C 衍生物,水溶性,适合敏感肌",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "抗坏血酸磷酸酯钠": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "即 SAP,维 C 衍生物,稳定美白",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "抗坏血酸棕榈酸酯": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "维 C 酯,脂溶性,抗氧化兼美白",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "传明酸": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "即氨甲环酸,抑制黑色素传输,温和高效",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版) 最大允许浓度 3%",
    },
    "4-丁基间苯二酚": {
        "category": "美白成分",
        "risk_level": "注意",
        "description": "高效酪氨酸酶抑制剂,美白力强,需控制浓度防刺激",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "己基间苯二酚": {
        "category": "美白成分",
        "risk_level": "注意",
        "description": "即 HR,美白兼抗氧化,可能刺激",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "苯乙基间苯二酚": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "即 SymWhite 377,高效美白剂,稳定低刺激",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版) 最大允许浓度 0.5%",
    },
    "光甘草定": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "光果甘草提取物,高效酪氨酸酶抑制,温和",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "α-熊果苷": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "即 Alpha-Arbutin,高效熊果苷异构体,美白力强",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版) 最大允许浓度 2%",
    },
    "β-熊果苷": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "传统熊果苷,温和美白,稳定性较 α 型略低",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版) 最大允许浓度 7%",
    },
    "脱氧熊果苷": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "D-Arbutin,熊果苷衍生物,稳定性更高",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "曲酸": {
        "category": "美白成分",
        "risk_level": "注意",
        "description": "真菌代谢产物,酪氨酸酶抑制剂,可能致敏",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "鞣花酸": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "植物多酚,抗氧化兼美白,温和",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "丹皮酚": {
        "category": "美白成分",
        "risk_level": "注意",
        "description": "牡丹皮提取物,美白抗炎,高浓度可能刺激",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "烟酰胺己酸": {
        "category": "美白成分",
        "risk_level": "安全",
        "description": "烟酰胺衍生物,美白兼控油,温和",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },

    # ===== 更多表面活性剂(10种) =====
    "月桂醇聚醚硫酸酯铵": {
        "category": "表面活性剂",
        "risk_level": "注意",
        "description": "铵盐 SLES,温和度优于钠盐,常用于氨基酸洗发水",
        "reference": "CIR 评估认为安全",
    },
    "月桂醇硫酸酯铵": {
        "category": "表面活性剂",
        "risk_level": "注意",
        "description": "铵盐 SLS,清洁力强,刺激性较 SLS 略低",
        "reference": "CIR 评估认为安全",
    },
    "椰油酰羟乙磺酸酯钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "即 SCI,温和固体表活,常用于洁面皂、氨基酸洁面",
        "reference": "CIR 评估认为安全",
    },
    "月桂酰甲基羟乙磺酸酯钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "温和羟乙磺酸表活,适合敏感肌",
        "reference": "CIR 评估认为安全",
    },
    "椰油酰基谷氨酸二钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "氨基酸表活,温和亲肤,起泡性较弱",
        "reference": "CIR 评估认为安全",
    },
    "月桂酰肌氨酸钾": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "肌氨酸盐表活,温和低刺激,有抑菌辅助",
        "reference": "CIR 评估认为安全",
    },
    "油酰氨基甲基牛磺酸钠": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "即 月桂酰基牛磺酸钠,温和表活,适合洁面",
        "reference": "CIR 评估认为安全",
    },
    "椰油酰胺甲基MEA": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "增泡增稠剂,辅助表活",
        "reference": "CIR 评估认为安全",
    },
    "PEG-7 甘油椰油酸酯": {
        "category": "表面活性剂",
        "risk_level": "安全",
        "description": "温和增溶乳化剂,常作辅助表活",
        "reference": "CIR 评估认为安全",
    },
    "十六烷基三甲基溴化铵": {
        "category": "表面活性剂",
        "risk_level": "注意",
        "description": "CTAB,阳离子表活,护发调理,高浓度刺激",
        "reference": "CIR 评估认为安全",
    },

    # ===== 乳化剂(8种) =====
    "鲸蜡硬脂醇聚醚-20": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "非离子乳化剂,常作主乳化剂",
        "reference": "CIR 评估认为安全",
    },
    "聚山梨醇酯-60": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "吐温60,乳化增溶,温和",
        "reference": "CIR 评估认为安全",
    },
    "聚山梨醇酯-80": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "吐温80,乳化增溶,常见于乳液",
        "reference": "CIR 评估认为安全",
    },
    "失水山梨醇硬脂酸酯": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "即 Span 60,辅助乳化剂,与吐温复配",
        "reference": "CIR 评估认为安全",
    },
    "失水山梨醇油酸酯": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "即 Span 80,辅助乳化剂",
        "reference": "CIR 评估认为安全",
    },
    "聚甘油-3 甲基葡糖二硬脂酸酯": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "PEG-free 乳化剂,温和亲肤",
        "reference": "CIR 评估认为安全",
    },
    "卵磷脂": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "天然磷脂,乳化兼修护,温和",
        "reference": "CIR 评估认为安全",
    },
    "硬脂醇聚醚-2": {
        "category": "乳化剂",
        "risk_level": "安全",
        "description": "非离子乳化剂,常与硬脂醇聚醚-21 复配",
        "reference": "CIR 评估认为安全",
    },

    # ===== 脂质/油脂(10种) =====
    "甜杏仁油": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "植物油,保湿滋润,温和亲肤",
        "reference": "CIR 评估认为安全",
    },
    "油橄榄果油": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "即橄榄油,滋润抗氧化",
        "reference": "CIR 评估认为安全",
    },
    "神经酰胺 3": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "屏障修复核心成分,补充细胞间脂质",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "神经酰胺 6 II": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "屏障修复,平滑角质",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "神经酰胺 1": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "屏障修复,锁水保湿",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "胆固醇": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "细胞间脂质,与神经酰胺协同修护屏障",
        "reference": "CIR 评估认为安全",
    },
    "月见草油": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "γ-亚麻酸丰富,修护舒缓",
        "reference": "CIR 评估认为安全",
    },
    "玫瑰果油": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "富含维C,美白抗氧化",
        "reference": "CIR 评估认为安全",
    },
    "葡萄籽油": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "原花青素丰富,抗氧化",
        "reference": "CIR 评估认为安全",
    },
    "辛酸/癸酸甘油三酯": {
        "category": "油脂",
        "risk_level": "安全",
        "description": "即 MCT,清爽润肤,稳定性好",
        "reference": "CIR 评估认为安全",
    },

    # ===== 植物提取物(20种) =====
    "积雪草苷": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "积雪草活性成分,舒缓修复促进愈合",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "茶多酚": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "绿茶多酚,抗氧化抗炎",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "绿茶提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "抗氧化控油,温和",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "迷迭香叶提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "抗氧化抗菌控油",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "母菊提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "即洋甘菊,舒缓抗炎抗敏",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "金盏花提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "舒缓抗炎,温和适合敏感肌",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "库拉索芦荟叶汁粉": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "浓缩芦荟,保湿舒缓",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "红没药醇": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "洋甘菊活性成分,高效舒缓抗敏",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "白藜芦醇": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "抗氧化抗衰老,温和",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "表没食子儿茶素没食子酸酯": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "即 EGCG,绿茶主活性,强抗氧化",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "银杏叶提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "抗氧化促进微循环",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "人参根提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "滋补抗衰,促进胶原合成",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "当归根提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "活血提亮,美白辅助",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "黄芩根提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "抗氧化抗炎抑菌",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "苦参根提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "抑菌舒缓,去屑辅助",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "何首乌根提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "传统护发成分,乌发强韧",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "甘草根提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "美白抗炎舒缓,温和高效",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "姜根提取物": {
        "category": "植物提取物",
        "risk_level": "注意",
        "description": "促循环抗炎,高浓度可能刺激",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "北美金缕梅提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "收敛控油舒缓,温和",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "假叶树根提取物": {
        "category": "植物提取物",
        "risk_level": "安全",
        "description": "促进微循环,消浮肿,眼部护理常用",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },

    # ===== 口腔护理(10种) =====
    "磷酸氢钙二水合物": {
        "category": "研磨剂",
        "risk_level": "安全",
        "description": "温和研磨剂,高级透明牙膏常用",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "磷酸三钙": {
        "category": "研磨剂",
        "risk_level": "安全",
        "description": "温和研磨剂,与氟化物兼容性较好",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "氢氧化铝": {
        "category": "研磨剂",
        "risk_level": "安全",
        "description": "研磨剂,常用于美白牙膏",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "焦磷酸四钠": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "防牙石,螯合钙离子",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "焦磷酸四钾": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "防牙石,与焦磷酸四钠协同",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "三聚磷酸五钠": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "防牙石,螯合剂",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "硅酸铝镁": {
        "category": "增稠剂",
        "risk_level": "安全",
        "description": "天然矿物增稠悬浮剂,牙膏常用",
        "reference": "常用成分，未见安全风险报告",
    },
    "三氯半乳蔗糖": {
        "category": "甜味剂",
        "risk_level": "安全",
        "description": "即蔗糖素,高强度甜味剂,牙膏常用",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "缩水磷酸钠": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "防龋防牙石,稳定氟化物",
        "reference": "《牙膏用原料规范》GB 22115-2008 允许使用的牙膏原料",
    },
    "植酸钠": {
        "category": "防龋成分",
        "risk_level": "安全",
        "description": "天然螯合剂,防牙石美白",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },

    # ===== 抗敏/舒缓成分(10种) =====
    "4-叔丁基环己醇": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "即 SymSitive 1609,神经敏感舒缓,快速退红",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "二氢燕麦生物碱": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "即 Dihydroavenanthramide D,强效舒缓抗炎",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "羟基积雪草苷": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "积雪草主活性,舒缓修复促进愈合",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "甘草酸二钾": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "甘草酸衍生物,抗炎舒缓,温和",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "甘草酸铵": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "甘草酸盐,抗炎抗敏",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "甘草酸硬脂酯": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "脂溶性甘草酸,渗透性好",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "龙胆根提取物": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "舒缓抗炎提亮",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "羟基积雪草酸": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "积雪草活性,与羟基积雪草苷协同",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "积雪草酸": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "积雪草活性,促进胶原合成",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "泛醇钙": {
        "category": "抗敏成分",
        "risk_level": "安全",
        "description": "B5 衍生物,舒缓修护",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },

    # ===== 香料成分(12种) =====
    "芳樟醇": {
        "category": "香精",
        "risk_level": "注意",
        "description": "常见香精成分,易致敏,欧盟需标注",
        "reference": "《化妆品安全技术规范》(2015版) 香精过敏原标签要求；欧盟 (EC) No 1223/2009 必须标注",
    },
    "香叶醇": {
        "category": "香精",
        "risk_level": "注意",
        "description": "玫瑰香气香精成分,易致敏",
        "reference": "欧盟 (EC) No 1223/2009 香精致敏原标签要求",
    },
    "柠檬烯": {
        "category": "香精",
        "risk_level": "注意",
        "description": "柑橘香气,氧化后易致敏",
        "reference": "欧盟 (EC) No 1223/2009 香精致敏原标签要求",
    },
    "香茅醇": {
        "category": "香精",
        "risk_level": "注意",
        "description": "玫瑰香气,欧盟需标注致敏原",
        "reference": "欧盟 (EC) No 1223/2009 香精致敏原标签要求",
    },
    "丁香酚": {
        "category": "香精",
        "risk_level": "注意",
        "description": "丁香气味,易致敏",
        "reference": "欧盟 (EC) No 1223/2009 香精致敏原标签要求",
    },
    "肉桂醛": {
        "category": "香精",
        "risk_level": "注意",
        "description": "肉桂气味,强致敏原,需低浓度使用",
        "reference": "欧盟 (EC) No 1223/2009 香精致敏原标签要求；IFRA 限量",
    },
    "香豆素": {
        "category": "香精",
        "risk_level": "注意",
        "description": "草木香气,欧盟需标注",
        "reference": "欧盟 (EC) No 1223/2009 香精致敏原标签要求",
    },
    "羟基香茅醛": {
        "category": "香精",
        "risk_level": "注意",
        "description": "花香香气,欧盟需标注",
        "reference": "欧盟 (EC) No 1223/2009 香精致敏原标签要求",
    },
    "异丁香酚": {
        "category": "香精",
        "risk_level": "注意",
        "description": "丁香衍生物,易致敏",
        "reference": "欧盟 (EC) No 1223/2009 香精致敏原标签要求",
    },
    "橡苔提取物": {
        "category": "香精",
        "risk_level": "注意",
        "description": "橡苔树脂,强致敏原,IFRA 严格限量",
        "reference": "IFRA 标准 (10th Amendment) 限用",
    },
    "香兰素": {
        "category": "香精",
        "risk_level": "安全",
        "description": "香草香气,温和食用级香料",
        "reference": "常用成分，未见安全风险报告",
    },
    "苯乙醇": {
        "category": "香精",
        "risk_level": "安全",
        "description": "玫瑰香气,温和",
        "reference": "CIR 评估认为安全",
    },

    # ===== 其他活性/添加剂(18种) =====
    "乳酸": {
        "category": "缓冲剂",
        "risk_level": "安全",
        "description": "pH 调节兼保湿,温和果酸",
        "reference": "常用成分，未见安全风险报告",
    },
    "苹果酸": {
        "category": "缓冲剂",
        "risk_level": "安全",
        "description": "果酸,温和去角质",
        "reference": "《化妆品安全技术规范》(2015版) 限用成分（α-羟基酸）",
    },
    "酒石酸": {
        "category": "缓冲剂",
        "risk_level": "安全",
        "description": "果酸,pH 调节兼去角质",
        "reference": "《化妆品安全技术规范》(2015版) 限用成分（α-羟基酸）",
    },
    "磷酸": {
        "category": "缓冲剂",
        "risk_level": "注意",
        "description": "pH 调节剂,高浓度腐蚀性",
        "reference": "常用成分，未见安全风险报告",
    },
    "氢氧化钠": {
        "category": "缓冲剂",
        "risk_level": "注意",
        "description": "pH 调节剂,高浓度腐蚀性,产品中需中和",
        "reference": "常用成分，未见安全风险报告",
    },
    "三乙醇胺": {
        "category": "缓冲剂",
        "risk_level": "注意",
        "description": "pH 调节兼乳化,有争议但常规使用安全",
        "reference": "CIR 评估认为安全",
    },
    "氨甲基丙醇": {
        "category": "缓冲剂",
        "risk_level": "安全",
        "description": "即 AMP-95,pH 调节剂,温和",
        "reference": "CIR 评估认为安全",
    },
    "羟基亚乙基二膦酸": {
        "category": "螯合剂",
        "risk_level": "安全",
        "description": "即 HEDP,高效螯合稳定剂",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "苯并异噻唑啉酮": {
        "category": "防腐剂",
        "risk_level": "注意",
        "description": "即 BIT,防腐剂,致敏性较 MIT 低",
        "reference": "《化妆品安全技术规范》(2015版) 限用防腐剂，最大允许浓度 0.01%",
    },
    "辛甘醇": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "即 Caprylyl Glycol,保湿兼防腐辅助",
        "reference": "CIR 评估认为安全",
    },
    "乙基己基甘油": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "即 EHG,保湿兼防腐增效,温和",
        "reference": "CIR 评估认为安全",
    },
    "1,2-己二醇": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "保湿兼防腐辅助,温和",
        "reference": "CIR 评估认为安全",
    },
    "戊二醇": {
        "category": "保湿剂",
        "risk_level": "安全",
        "description": "即 1,2-戊二醇,保湿防腐辅助",
        "reference": "CIR 评估认为安全",
    },
    "聚季铵盐-7": {
        "category": "调理剂",
        "risk_level": "安全",
        "description": "阳离子调理剂,护发定型",
        "reference": "CIR 评估认为安全",
    },
    "聚季铵盐-10": {
        "category": "调理剂",
        "risk_level": "安全",
        "description": "阳离子调理剂,洗发水顺滑感",
        "reference": "CIR 评估认为安全",
    },
    "聚季铵盐-22": {
        "category": "调理剂",
        "risk_level": "安全",
        "description": "阳离子调理剂,保湿定型",
        "reference": "CIR 评估认为安全",
    },
    "二甲砜": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "即 MSM,有机硫,舒缓关节,护肤温和",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
    },
    "视黄醇棕榈酸酯": {
        "category": "活性成分",
        "risk_level": "安全",
        "description": "即维 A 酯,温和抗老,孕妇慎用",
        "reference": "国家药监局《化妆品已使用原料目录》(2021版)",
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
    # 防晒剂
    "阿伏苯宗": "丁基甲氧基二苯甲酰甲烷",
    "avobenzone": "丁基甲氧基二苯甲酰甲烷",
    "butyl methoxydibenzoylmethane": "丁基甲氧基二苯甲酰甲烷",
    "桂皮酸盐": "甲氧基肉桂酸乙基己酯",
    "octinoxate": "甲氧基肉桂酸乙基己酯",
    "ethylhexyl methoxycinnamate": "甲氧基肉桂酸乙基己酯",
    "octocrylene": "奥克立林",
    "二苯酮3": "二苯酮-3",
    "oxybenzone": "二苯酮-3",
    "benzophenone-3": "二苯酮-3",
    "二苯酮4": "二苯酮-4",
    "benzophenone-4": "二苯酮-4",
    "水杨酸辛酯": "水杨酸乙基己酯",
    "octisalate": "水杨酸乙基己酯",
    "水杨酸三甲环己酯": "胡莫柳酯",
    "homosalate": "胡莫柳酯",
    "tinosorb s": "双-乙基己氧苯酚甲氧苯基三嗪",
    "双-乙基己氧苯酚甲氧苯基三嗪": "双-乙基己氧苯酚甲氧苯基三嗪",
    "tinosorb m": "亚甲基双-苯并三唑基四甲基丁基酚",
    "paba": "对氨基苯甲酸",
    "titanium dioxide": "二氧化钛",
    "zinc oxide": "氧化锌",
    "parsol slx": "聚硅氧烷-15",
    # 染发剂
    "ppd": "对苯二胺",
    "p-phenylenediamine": "对苯二胺",
    "对苯二胺": "对苯二胺",
    "ptd": "对甲苯二胺",
    "p-toluenediamine": "对甲苯二胺",
    "resorcinol": "间苯二酚",
    "间苯二酚": "间苯二酚",
    # 美白成分
    "氨甲环酸": "传明酸",
    "tranexamic acid": "传明酸",
    "eae": "3-邻-乙基抗坏血酸",
    "3-o-ethyl ascorbic acid": "3-邻-乙基抗坏血酸",
    "aa2g": "抗坏血酸葡糖苷",
    "ascorbyl glucoside": "抗坏血酸葡糖苷",
    "map": "抗坏血酸磷酸酯镁",
    "ascorbyl phosphate magnesium": "抗坏血酸磷酸酯镁",
    "sap": "抗坏血酸磷酸酯钠",
    "ascorbyl phosphate sodium": "抗坏血酸磷酸酯钠",
    "ascorbyl palmitate": "抗坏血酸棕榈酸酯",
    "377": "苯乙基间苯二酚",
    "symwhite 377": "苯乙基间苯二酚",
    "phenylethyl resorcinol": "苯乙基间苯二酚",
    "alpha-arbutin": "α-熊果苷",
    "α-arbutin": "α-熊果苷",
    "beta-arbutin": "β-熊果苷",
    "β-arbutin": "β-熊果苷",
    "arbutin": "β-熊果苷",
    "熊果苷": "β-熊果苷",
    "d-arbutin": "脱氧熊果苷",
    "deoxyarbutin": "脱氧熊果苷",
    "kojic acid": "曲酸",
    "ellagic acid": "鞣花酸",
    "光甘草定": "光甘草定",
    "glabridin": "光甘草定",
    "传明酸": "传明酸",
    # 第 2/3 批补充
    # 表活
    "ammonium laureth sulfate": "月桂醇聚醚硫酸酯铵",
    "ammonium lauryl sulfate": "月桂醇硫酸酯铵",
    "sci": "椰油酰羟乙磺酸酯钠",
    "sodium cocoyl isethionate": "椰油酰羟乙磺酸酯钠",
    "sodium lauroyl methyl isethionate": "月桂酰甲基羟乙磺酸酯钠",
    "sodium cocoyl glutamate disodium": "椰油酰基谷氨酸二钠",
    "potassium lauroyl sarcosinate": "月桂酰肌氨酸钾",
    "sodium methyl cocoyl taurate": "油酰氨基甲基牛磺酸钠",
    "ctab": "十六烷基三甲基溴化铵",
    "cetyltrimethyl ammonium bromide": "十六烷基三甲基溴化铵",
    # 乳化剂
    "ceteareth-20": "鲸蜡硬脂醇聚醚-20",
    "tween 60": "聚山梨醇酯-60",
    "tween 80": "聚山梨醇酯-80",
    "聚山梨醇酯60": "聚山梨醇酯-60",
    "聚山梨醇酯80": "聚山梨醇酯-80",
    "span 60": "失水山梨醇硬脂酸酯",
    "span 80": "失水山梨醇油酸酯",
    "lecithin": "卵磷脂",
    "steareth-2": "硬脂醇聚醚-2",
    # 油脂
    "橄榄油": "油橄榄果油",
    "olive oil": "油橄榄果油",
    "胆固醇": "胆固醇",
    "cholesterol": "胆固醇",
    "ceramide 3": "神经酰胺 3",
    "ceramide 6 ii": "神经酰胺 6 II",
    "ceramide 1": "神经酰胺 1",
    "月见草油": "月见草油",
    "evening primrose oil": "月见草油",
    "玫瑰果油": "玫瑰果油",
    "rose hip oil": "玫瑰果油",
    "葡萄籽油": "葡萄籽油",
    "grape seed oil": "葡萄籽油",
    "mct": "辛酸/癸酸甘油三酯",
    "caprylic/capric triglyceride": "辛酸/癸酸甘油三酯",
    "辛酸癸酸甘油三酯": "辛酸/癸酸甘油三酯",
    # 植物提取物
    "洋甘菊": "母菊提取物",
    "chamomile": "母菊提取物",
    "金缕梅": "北美金缕梅提取物",
    "witch hazel": "北美金缕梅提取物",
    "egcg": "表没食子儿茶素没食子酸酯",
    "resveratrol": "白藜芦醇",
    "bisabolol": "红没药醇",
    "α-bisabolol": "红没药醇",
    # 抗敏
    "symsitive 1609": "4-叔丁基环己醇",
    "symcalmin": "二氢燕麦生物碱",
    "dihydroavenanthramide d": "二氢燕麦生物碱",
    "甘草酸二钾": "甘草酸二钾",
    "dipotassium glycyrrhizate": "甘草酸二钾",
    "ammonium glycyrrhizate": "甘草酸铵",
    # 口腔护理
    "蔗糖素": "三氯半乳蔗糖",
    "sucralose": "三氯半乳蔗糖",
    "植酸钠": "植酸钠",
    "sodium phytate": "植酸钠",
    # 缓冲剂/螯合剂
    "lactic acid": "乳酸",
    "malic acid": "苹果酸",
    "tartaric acid": "酒石酸",
    "phosphoric acid": "磷酸",
    "sodium hydroxide": "氢氧化钠",
    "naoh": "氢氧化钠",
    "triethanolamine": "三乙醇胺",
    "tea": "三乙醇胺",
    "amp-95": "氨甲基丙醇",
    "aminomethyl propanol": "氨甲基丙醇",
    "hedp": "羟基亚乙基二膦酸",
    # 防腐/保湿辅助
    "bit": "苯并异噻唑啉酮",
    "caprylyl glycol": "辛甘醇",
    "ehg": "乙基己基甘油",
    "ethylhexylglycerin": "乙基己基甘油",
    "1,2-hexanediol": "1,2-己二醇",
    "1,2-pentanediol": "戊二醇",
    # 调理剂
    "polyquaternium-7": "聚季铵盐-7",
    "polyquaternium-10": "聚季铵盐-10",
    "polyquaternium-22": "聚季铵盐-22",
    "聚季铵盐7": "聚季铵盐-7",
    "聚季铵盐10": "聚季铵盐-10",
    "聚季铵盐22": "聚季铵盐-22",
    # 其他
    "msm": "二甲砜",
    "methylsulfonylmethane": "二甲砜",
    "retinyl palmitate": "视黄醇棕榈酸酯",
    "维a酯": "视黄醇棕榈酸酯",
    # 香料
    "linalool": "芳樟醇",
    "geraniol": "香叶醇",
    "limonene": "柠檬烯",
    "citronellol": "香茅醇",
    "eugenol": "丁香酚",
    "cinnamal": "肉桂醛",
    "cinnamaldehyde": "肉桂醛",
    "coumarin": "香豆素",
    "hydroxycitronellal": "羟基香茅醛",
    "isoeugenol": "异丁香酚",
    "vanillin": "香兰素",
    "phenethyl alcohol": "苯乙醇",
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
        # 成分数据来自 SQLite 数据库,无需在内存中持有字典
        # INGREDIENT_DB / SYNONYMS 仍保留在文件中,供 seed.py 读取导入
        pass

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

            # 同义词归一 + 数据库查询(find_ingredient 一次搞定)
            info = find_ingredient(item)
            # 用标准名去重(数据库返回的是标准名,未入库的用原始名)
            standard_name = info["name"] if info else item
            if standard_name in seen:
                continue
            seen.add(standard_name)

            if info:
                results.append(IngredientInfo(
                    name=info["name"],
                    category=info["category"],
                    risk_level=info["risk_level"],
                    description=info["description"],
                    in_database=True,
                    reference=info.get("reference") or "",
                ))
            else:
                # 未在库中,仍记录(LLM 兜底分析)
                results.append(IngredientInfo(
                    name=item,
                    in_database=False,
                    reference="LLM 分析,未经数据库核实",
                ))

        return results
