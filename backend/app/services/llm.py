"""DeepSeek LLM 分析服务

负责将配料表文字转化为用户易懂的"优缺点"分析。
"""
import asyncio
import json
import re
import time

import httpx

from app.config import settings
from app.logger import logger
from app.models.schemas import AnalysisResult, IngredientInfo

# 重试配置
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # LLM 重试间隔比 OCR 长(避免 rate limit)


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
        """分析成分并生成优缺点(带重试机制)

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

        start_time = time.time()
        logger.info(f"开始 LLM 分析,成分数量: {len(ingredients)},模型: {self.model}")

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

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                # 记录 token 用量(如果返回)
                usage = data.get("usage", {})
                if usage:
                    logger.info(
                        f"LLM token 用量 - 提示: {usage.get('prompt_tokens', '?')}, "
                        f"完成: {usage.get('completion_tokens', '?')}, "
                        f"总计: {usage.get('total_tokens', '?')}"
                    )

                # 响应结构解析保护(避免 KeyError/IndexError)
                try:
                    content = data["choices"][0]["message"]["content"].strip()
                except (KeyError, IndexError, TypeError):
                    logger.error(f"LLM 响应结构异常: {json.dumps(data, ensure_ascii=False)[:500]}")
                    return AnalysisResult(
                        pros=[], cons=[], score=0,
                        summary="LLM 响应结构异常,请重试",
                    )

                # 用正则提取 JSON 对象,兼容 markdown 代码块和前后多余文本
                json_match = re.search(r'\{[\s\S]*\}', content)
                if not json_match:
                    logger.warning(f"LLM 输出无法解析为 JSON,原始内容: {content[:300]}")
                    return AnalysisResult(
                        pros=[], cons=[], score=0,
                        summary="分析结果解析失败,请重试",
                    )

                try:
                    result = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    logger.warning(f"LLM JSON 解析失败,原始内容: {json_match.group(0)[:300]}")
                    return AnalysisResult(
                        pros=[], cons=[], score=0,
                        summary="分析结果解析失败,请重试",
                    )

                # AnalysisResult 构造保护(避免 pydantic ValidationError)
                try:
                    analysis = AnalysisResult(
                        pros=result.get("pros", []),
                        cons=result.get("cons", []),
                        score=result.get("score", 0),
                        summary=result.get("summary", ""),
                        product_type=result.get("product_type", ""),
                    )
                except Exception:
                    logger.error(f"AnalysisResult 构造失败: {result}")
                    return AnalysisResult(
                        pros=[], cons=[], score=0,
                        summary="分析结果格式异常,请重试",
                    )

                elapsed = time.time() - start_time
                logger.info(
                    f"LLM 分析成功,评分: {analysis.score}, 产品类型: {analysis.product_type}, "
                    f"耗时 {elapsed:.2f}s"
                )
                return analysis

            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code
                # 4xx 错误(如 401 认证失败、400 请求格式错误)不重试
                if 400 <= status_code < 500 and status_code != 429:
                    logger.error(f"LLM 请求失败(HTTP {status_code}),不重试: {e}")
                    raise RuntimeError(f"DeepSeek API 请求失败(HTTP {status_code})")
                logger.warning(f"LLM 第 {attempt + 1} 次尝试失败(HTTP {status_code}): {e}")

            except httpx.HTTPError as e:
                last_error = e
                logger.warning(f"LLM 第 {attempt + 1} 次网络错误: {type(e).__name__}: {e}")

            # 指数退避等待(最后一次不等待)
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.info(f"等待 {delay}s 后重试...")
                await asyncio.sleep(delay)

        elapsed = time.time() - start_time
        logger.error(f"LLM 分析彻底失败,重试 {MAX_RETRIES} 次后仍报错,总耗时 {elapsed:.2f}s")
        raise RuntimeError(f"LLM 分析失败(重试 {MAX_RETRIES} 次): {last_error}")
