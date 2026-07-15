"""客观评分计算模块

基于成分库风险等级计算产品评分,替代 LLM 主观评分。
评分更稳定、可复现、有据可查。

评分规则:
- 基础分 100
- 风险扣分(按比例)= (注意数×1.5 + 慎用数×4 + 规避数×9 + 未知数×2) / 总数 × 10
- 评分 = 100 - 风险扣分,范围 0-100

设计思路:
- 按比例计算,避免成分越多分越低(30个全慎用和10个全慎用分数相同)
- 规避成分扣分最重(9),慎用次之(4),注意最轻(1.5)
- 未入库成分按"未知风险"处理,权重 2(高于安全0,低于注意1.5)
  避免未入库成分被当作安全成分导致评分虚高

等级划分:
- 86-100:优秀(成分安全温和,推荐使用)
- 76-85:良好(成分整体不错,可放心使用)
- 60-75:一般(部分成分需留意,按需选择)
- 0-59:不推荐(含有较多风险成分,建议谨慎)
"""
from app.logger import logger
from app.models.schemas import IngredientInfo

# 风险等级对应的扣分权重
RISK_WEIGHTS = {
    "安全": 0,
    "注意": 1.5,
    "慎用": 4,
    "规避": 9,
    "未知": 2,  # 未入库成分,风险未知,给中性扣分
}


def calculate_score(ingredients: list[IngredientInfo]) -> int:
    """根据成分风险等级计算客观评分

    Args:
        ingredients: 已匹配的成分列表(含 risk_level 字段)

    Returns:
        0-100 的整数评分
    """
    total = len(ingredients)

    # 无成分时给默认分(避免除零,也给个中性分)
    if total == 0:
        return 80

    # 统计各风险等级数量
    counts = {"安全": 0, "注意": 0, "慎用": 0, "规避": 0, "未知": 0}
    for ing in ingredients:
        level = ing.risk_level if ing.risk_level in counts else "未知"
        counts[level] += 1

    # 计算风险扣分(按比例)
    # 未入库成分(未知风险)按权重 2 扣分,避免评分虚高
    risk_penalty = (
        counts["注意"] * RISK_WEIGHTS["注意"]
        + counts["慎用"] * RISK_WEIGHTS["慎用"]
        + counts["规避"] * RISK_WEIGHTS["规避"]
        + counts["未知"] * RISK_WEIGHTS["未知"]
    ) / total * 10

    score = 100 - risk_penalty

    # 限制在 0-100 范围
    score = max(0, min(100, score))

    final_score = round(score)
    logger.info(
        f"评分计算:总成分 {total},安全 {counts['安全']},注意 {counts['注意']},"
        f"慎用 {counts['慎用']},规避 {counts['规避']},未知 {counts['未知']},"
        f"扣分 {risk_penalty:.1f},最终评分 {final_score}"
    )
    return final_score


def get_score_grade(score: int) -> dict:
    """获取评分等级信息

    Args:
        score: 0-100 的评分

    Returns:
        dict: { label, desc, color }
    """
    if score >= 86:
        return {"label": "优秀", "desc": "成分安全温和,推荐使用", "color": "#00b894"}
    elif score >= 76:
        return {"label": "良好", "desc": "成分整体不错,可放心使用", "color": "#0984e3"}
    elif score >= 60:
        return {"label": "一般", "desc": "部分成分需留意,按需选择", "color": "#fdcb6e"}
    else:
        return {"label": "不推荐", "desc": "含有较多风险成分,建议谨慎", "color": "#d63031"}
