"""DeepSeek LLM 分析服务

负责将配料表文字转化为用户易懂的"优缺点"分析。
"""
import json
import re

import httpx

from app.config import settings
from app.models.schemas import AnalysisResult, IngredientInfo


class DeepSeekService:
    """DeepSeek 大模型分析服务"""

    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url
        self.model = settings.deepseek_model

    async def analyze_ingredients(
        self,
        raw_text: str,
        ingredients: list[IngredientInfo],
    ) -> AnalysisResult:
        """分析成分并生成优缺点

        Args:
            raw_text: OCR 识别的配料表原文
            ingredients: 已匹配的成分列表

        Returns:
            AnalysisResult: 优缺点、评分、总结
        """
        if not self.api_key:
            raise RuntimeError(
                "DeepSeek API Key 未配置,请在 .env 中设置 DEEPSEEK_API_KEY"
            )

        # 构造成分清单(标注库中已知信息)
        ingredient_lines = []
        for ing in ingredients:
            line = f"- {ing.name}"
            if ing.in_database and ing.category:
                line += f"(分类:{ing.category},风险:{ing.risk_level})"
            ingredient_lines.append(line)
        ingredient_list = "\n".join(ingredient_lines) if ingredient_lines else "无"

        prompt = f"""你是一位专业的日化洗护产品成分分析师。请根据以下配料表信息,分析产品的优缺点。

【配料表原文】
{raw_text}

【已识别成分(含库中已知信息)】
{ingredient_list}

分析要求:
1. 产品品类:从配料表原文和使用方法中判断产品类型(如:洗发水、护发素、沐浴露、牙膏、漱口水、面霜、乳液、精华、洗手液、洗衣液等)
2. 优点:产品中含有的对消费者有益的成分或配方特点
3. 缺点:可能存在刺激性、致敏性、安全性争议的成分(如 SLS、尼泊金酯等)
4. 评分:0-100,越高越好(60以下为不推荐,60-75为一般,76-85为良好,86以上为优秀)
5. 总结:一句话概括产品整体情况

请严格按以下 JSON 格式输出,不要输出任何其他内容(不要 markdown 代码块标记):
{{
  "product_type": "洗发水",
  "pros": ["优点1", "优点2"],
  "cons": ["缺点1", "缺点2"],
  "score": 75,
  "summary": "一句话总结"
}}"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,  # 低温度保证输出稳定
        }

        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # 响应结构解析保护(避免 KeyError/IndexError)
        try:
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            return AnalysisResult(
                pros=[], cons=[], score=0,
                summary="LLM 响应结构异常,请重试",
            )

        # 用正则提取 JSON 对象,兼容 markdown 代码块和前后多余文本
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            return AnalysisResult(
                pros=[], cons=[], score=0,
                summary="分析结果解析失败,请重试",
            )

        try:
            result = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return AnalysisResult(
                pros=[], cons=[], score=0,
                summary="分析结果解析失败,请重试",
            )

        # AnalysisResult 构造保护(避免 pydantic ValidationError)
        try:
            return AnalysisResult(
                pros=result.get("pros", []),
                cons=result.get("cons", []),
                score=result.get("score", 0),
                summary=result.get("summary", ""),
                product_type=result.get("product_type", ""),
            )
        except Exception:
            return AnalysisResult(
                pros=[], cons=[], score=0,
                summary="分析结果格式异常,请重试",
            )
