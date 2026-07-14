"""成分相互作用与替代建议服务

定义常见成分冲突规则和替代建议,在分析时自动检测。
规则基于皮肤科和化妆品配方常识,关键词匹配支持同义词/别名。
"""
from app.models.schemas import InteractionWarning, AlternativeSuggestion


# ===== 成分冲突规则 =====
# 每条规则定义两组关键词,当产品中同时出现 A 组和 B 组的成分时触发预警
# keywords 支持精确匹配和包含匹配(成分名包含任一关键词即命中)
INTERACTION_RULES: list[dict] = [
    {
        "keywords_a": ["视黄醇", "维生素A", "维A醇", "A醇", "retinol"],
        "keywords_b": ["水杨酸", "BHA"],
        "reason": "视黄醇(维A衍生物)与水杨酸(BHA)同用会过度刺激皮肤,建议分早晚使用",
        "severity": "高",
    },
    {
        "keywords_a": ["视黄醇", "维生素A", "维A醇", "A醇", "retinol"],
        "keywords_b": ["甘醇酸", "乳酸", "果酸", "AHA", "羟基乙酸"],
        "reason": "视黄醇与果酸(AHA)同用会增加刺激性,建议间隔使用",
        "severity": "高",
    },
    {
        "keywords_a": ["视黄醇", "维生素A", "维A醇", "A醇", "retinol"],
        "keywords_b": ["抗坏血酸", "维生素C", "维C", "VC"],
        "reason": "视黄醇与高浓度维生素C酸碱性冲突,可能降低功效,建议分早晚使用",
        "severity": "中",
    },
    {
        "keywords_a": ["烟酰胺"],
        "keywords_b": ["抗坏血酸", "维生素C", "维C", "VC"],
        "reason": "烟酰胺在酸性环境下可能转化为烟酸引起刺激,建议分早晚使用",
        "severity": "中",
    },
    {
        "keywords_a": ["过氧化苯甲酰", "benzoyl peroxide"],
        "keywords_b": ["视黄醇", "维生素A", "维A醇", "A醇", "retinol"],
        "reason": "过氧化苯甲酰会氧化视黄醇使其失效,建议分时段使用",
        "severity": "高",
    },
    {
        "keywords_a": ["铜肽", "蓝铜肽", "copper peptide"],
        "keywords_b": ["抗坏血酸", "维生素C", "维C", "VC"],
        "reason": "铜肽与维生素C会互相中和失效,建议分时段使用",
        "severity": "中",
    },
    {
        "keywords_a": ["苯甲醇"],
        "keywords_b": ["甲基异噻唑啉酮", "MIT", "甲基氯异噻唑啉酮", "CMIT"],
        "reason": "苯甲醇可能催化MIT/CMIT降解产生致敏物,敏感肌注意",
        "severity": "中",
    },
]


# ===== 成分替代规则 =====
# 对"慎用/规避"成分提供更温和的替代建议
ALTERNATIVE_RULES: list[dict] = [
    {
        "keywords": ["月桂醇硫酸酯钠", "SLS", "K12"],
        "reason": "刺激性较强的表面活性剂,可能引起皮肤干燥敏感",
        "alternatives": ["椰油酰谷氨酸钠", "月桂酰肌氨酸钠", "烷基糖苷", "椰油酰胺丙基甜菜碱"],
    },
    {
        "keywords": ["月桂醇聚醚硫酸酯钠", "SLES"],
        "reason": "清洁力强但生产过程可能残留二恶烷",
        "alternatives": ["椰油酰谷氨酸钠", "月桂酰肌氨酸钠", "烷基糖苷"],
    },
    {
        "keywords": ["对羟基苯甲酸甲酯", "对羟基苯甲酸乙酯", "对羟基苯甲酸丙酯", "对羟基苯甲酸丁酯", "尼泊金"],
        "reason": "尼泊金酯类防腐剂有内分泌干扰争议",
        "alternatives": ["苯氧乙醇", "苯甲酸钠", "山梨酸钾", "1,2-己二醇"],
    },
    {
        "keywords": ["甲基异噻唑啉酮", "MIT", "甲基氯异噻唑啉酮", "CMIT"],
        "reason": "高致敏性防腐剂,驻留类产品已禁用",
        "alternatives": ["苯氧乙醇", "1,2-己二醇", "对羟基苯乙酮"],
    },
    {
        "keywords": ["乙醇", "变性乙醇", "酒精"],
        "reason": "酒精可能引起皮肤干燥刺激,敏感肌慎用",
        "alternatives": ["丁二醇", "1,3-丙二醇", "双丙甘醇"],
    },
    {
        "keywords": ["十二烷基苯磺酸钠", "LAS"],
        "reason": "清洁力强但刺激性较大",
        "alternatives": ["椰油酰谷氨酸钠", "烷基糖苷", "月桂酰肌氨酸钠"],
    },
    {
        "keywords": ["椰油酰胺DEA"],
        "reason": "可能产生亚硝胺杂质",
        "alternatives": ["椰油酰胺MEA", "椰油酰胺丙基甜菜碱"],
    },
    {
        "keywords": ["咪唑烷基脲"],
        "reason": "甲醛释放型防腐剂,可能释放微量甲醛",
        "alternatives": ["苯氧乙醇", "苯甲酸钠", "山梨酸钾"],
    },
    {
        "keywords": ["异丙醇"],
        "reason": "挥发性溶剂,刺激性较强",
        "alternatives": ["丁二醇", "1,3-丙二醇", "双丙甘醇"],
    },
    {
        "keywords": ["脱氢乙酸"],
        "reason": "部分国家限制在化妆品中使用",
        "alternatives": ["苯氧乙醇", "苯甲酸钠", "山梨酸钾"],
    },
]


def _match_any_keyword(ingredient_name: str, keywords: list[str]) -> bool:
    """检查成分名是否包含任一关键词(大小写不敏感)"""
    name_lower = ingredient_name.lower()
    return any(kw.lower() in name_lower for kw in keywords)


def check_interactions(ingredient_names: list[str]) -> list[InteractionWarning]:
    """检测成分列表中的冲突组合

    Args:
        ingredient_names: 产品中所有成分名列表

    Returns:
        触发的冲突预警列表
    """
    warnings: list[InteractionWarning] = []
    for rule in INTERACTION_RULES:
        # 找出命中 A 组关键词的成分
        matched_a = [n for n in ingredient_names if _match_any_keyword(n, rule["keywords_a"])]
        # 找出命中 B 组关键词的成分
        matched_b = [n for n in ingredient_names if _match_any_keyword(n, rule["keywords_b"])]
        # 同时命中才触发
        if matched_a and matched_b:
            warnings.append(InteractionWarning(
                ingredient_a=matched_a[0],
                ingredient_b=matched_b[0],
                reason=rule["reason"],
                severity=rule["severity"],
            ))
    return warnings


def suggest_alternatives(
    ingredient_names: list[str],
    risk_levels: dict[str, str],
) -> list[AlternativeSuggestion]:
    """对"慎用/规避"成分生成替代建议

    Args:
        ingredient_names: 产品中所有成分名列表
        risk_levels: {成分名: 风险等级} 映射

    Returns:
        替代建议列表
    """
    suggestions: list[AlternativeSuggestion] = []
    seen_originals: set[str] = set()  # 去重(同一条规则可能命中多个成分)

    for rule in ALTERNATIVE_RULES:
        for name in ingredient_names:
            if name in seen_originals:
                continue
            if _match_any_keyword(name, rule["keywords"]):
                # 只对"慎用/规避"的成分建议替代
                risk = risk_levels.get(name, "")
                if risk in ("慎用", "规避"):
                    suggestions.append(AlternativeSuggestion(
                        original=name,
                        reason=rule["reason"],
                        alternatives=rule["alternatives"],
                    ))
                    seen_originals.add(name)
    return suggestions
