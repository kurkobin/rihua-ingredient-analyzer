"""API 路由"""
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models.schemas import AnalysisResponse
from app.services.ocr import BaiduOCRService
from app.services.llm import DeepSeekService
from app.services.ingredient import IngredientService

router = APIRouter()

# 服务实例(单例)
ocr_service = BaiduOCRService()
llm_service = DeepSeekService()
ingredient_service = IngredientService()

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_ingredient(image: UploadFile = File(...)):
    """分析商品配料表图片

    流程:图片 -> OCR -> 成分匹配 -> LLM 分析 -> 返回结果
    """
    # 1. 校验文件类型
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    # 2. 读取图片
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="图片内容为空")

    # 3. OCR 识别
    try:
        ocr_result = await ocr_service.recognize(image_bytes)
    except Exception as e:
        # 包含异常类型,避免消息为空时前端无法显示原因
        raise HTTPException(status_code=502, detail=f"OCR 识别失败: {type(e).__name__}: {e}")

    if not ocr_result.text.strip():
        raise HTTPException(status_code=422, detail="未识别到文字,请重新拍照或调整图片")

    # 4. 成分匹配
    ingredients = ingredient_service.match_ingredients(ocr_result.text)

    # 5. LLM 分析
    try:
        analysis = await llm_service.analyze_ingredients(
            raw_text=ocr_result.text,
            ingredients=ingredients,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM 分析失败: {e}")

    return AnalysisResponse(
        ocr_text=ocr_result.text,
        ingredients=ingredients,
        pros=analysis.pros,
        cons=analysis.cons,
        score=analysis.score,
        summary=analysis.summary,
        product_type=analysis.product_type,
    )
