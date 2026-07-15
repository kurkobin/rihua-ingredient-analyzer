"""API 路由"""
import hashlib
import json
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import Response

from app.database import (
    get_cache, set_cache,
    add_history, get_history_list, get_history_detail,
    delete_history, clear_history,
    search_ingredients, get_ingredient_categories,
    add_allergen, get_allergens, delete_allergen, get_allergen_names,
)
from app.limiter import limiter
from app.models.schemas import (
    AnalysisResponse, HistoryItem, HistoryDetail,
    CompareItem, CompareResponse,
    IngredientSearchItem, IngredientSearchResponse,
    AllergenItem, AllergenListResponse,
)
from app.services.ocr import BaiduOCRService
from app.services.llm import DeepSeekService
from app.services.ingredient import IngredientService
from app.services.pdf_service import generate_report_pdf
from app.services.interaction import check_interactions, suggest_alternatives
from app.services.scoring import calculate_score

router = APIRouter()

# 服务实例(单例)
ocr_service = BaiduOCRService()
llm_service = DeepSeekService()
ingredient_service = IngredientService()


@router.post("/analyze", response_model=AnalysisResponse)
@limiter.limit("5/minute")
async def analyze_ingredient(request: Request, image: UploadFile = File(...)):
    """分析商品配料表图片

    流程:图片 -> MD5 哈希 -> 查缓存 -> (命中则直接返回)
         -> (未命中)OCR -> 成分匹配 -> LLM 分析 -> 写缓存 + 写历史 -> 返回结果

    限流:每分钟 5 次/IP(OCR+LLM 成本高,防恶意刷量)
    """
    # 1. 校验文件类型
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    # 2. 读取图片(限制 10MB,防止大文件耗尽内存)
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="图片内容为空")
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="图片过大,请压缩到 10MB 以内后重试")

    # 3. 计算图片 MD5 哈希,查缓存
    img_hash = hashlib.md5(image_bytes).hexdigest()
    cached = get_cache(img_hash)
    if cached:
        # 缓存命中:直接返回,跳过 OCR 和 LLM
        return AnalysisResponse(**json.loads(cached))

    # 4. OCR 识别(缓存未命中时才执行)
    try:
        ocr_result = await ocr_service.recognize(image_bytes)
    except Exception as e:
        # 包含异常类型,避免消息为空时前端无法显示原因
        raise HTTPException(status_code=502, detail=f"OCR 识别失败: {type(e).__name__}: {e}")

    if not ocr_result.text.strip():
        raise HTTPException(status_code=422, detail="未识别到文字,请重新拍照或调整图片")

    # 5. 成分匹配
    ingredients = ingredient_service.match_ingredients(ocr_result.text)

    # 6. LLM 分析
    try:
        analysis = await llm_service.analyze_ingredients(
            raw_text=ocr_result.text,
            ingredients=ingredients,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM 分析失败: {e}")

    # 6.5 客观评分:基于成分库风险等级计算(覆盖 LLM 主观评分)
    # LLM 只负责生成优缺点文案和总结,评分由后端规则计算,更稳定可复现
    objective_score = calculate_score(ingredients)

    # 7. 组装结果,先写历史(拿到 history_id)再写缓存
    response = AnalysisResponse(
        ocr_text=ocr_result.text,
        ingredients=ingredients,
        pros=analysis.pros,
        cons=analysis.cons,
        score=objective_score,
        summary=analysis.summary,
        product_type=analysis.product_type,
    )

    # 8. 三大智能预警:成分冲突 + 过敏原 + 替代建议
    ingredient_names = [ing.name for ing in ingredients]
    # 8a. 成分相互作用检测
    response.interactions = check_interactions(ingredient_names)
    # 8b. 过敏原预警(检查用户档案中标记的过敏成分)
    allergen_names = get_allergen_names()
    if allergen_names:
        from app.models.schemas import AllergenAlert
        # 用集合交集快速找出命中的过敏成分
        hit_allergens = set(ingredient_names) & set(allergen_names)
        response.allergen_alerts = [AllergenAlert(ingredient_name=n) for n in sorted(hit_allergens)]
    # 8c. 成分替代建议(仅对"慎用/规避"成分)
    risk_levels = {ing.name: ing.risk_level for ing in ingredients if ing.risk_level}
    response.alternatives = suggest_alternatives(ingredient_names, risk_levels)

    # 先写入历史记录,拿到 history_id
    history_id = add_history(
        img_hash=img_hash,
        product_type=response.product_type,
        summary=response.summary,
        score=response.score,
        ingredient_count=len(response.ingredients),
        result_json=response.model_dump_json(),
    )
    # 设置 history_id 后再写缓存,确保缓存里的 JSON 包含 history_id
    response.history_id = history_id
    result_json = response.model_dump_json()
    set_cache(img_hash, result_json)

    return response


# ===== 历史记录接口 =====

@router.get("/history", response_model=list[HistoryItem])
def list_history(limit: int = 50):
    """获取历史记录列表(按时间倒序)"""
    return get_history_list(limit=limit)


@router.get("/history/{history_id}", response_model=HistoryDetail)
def get_history(history_id: int):
    """获取单条历史记录详情"""
    detail = get_history_detail(history_id)
    if not detail:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    return detail


@router.delete("/history/{history_id}")
@limiter.limit("20/minute")
def remove_history(request: Request, history_id: int):
    """删除一条历史记录"""
    if not delete_history(history_id):
        raise HTTPException(status_code=404, detail="历史记录不存在")
    return {"message": "已删除", "id": history_id}


@router.delete("/history")
@limiter.limit("10/minute")
def remove_all_history(request: Request):
    """清空全部历史记录"""
    count = clear_history()
    return {"message": f"已清空 {count} 条历史记录"}


# ===== 成分对比接口 =====

@router.get("/compare", response_model=CompareResponse)
@limiter.limit("20/minute")
def compare_history(request: Request, ids: str):
    """对比多条历史记录的成分差异

    参数:ids=1,2,3(逗号分隔的历史记录 id,至少 2 个)
    返回:各产品摘要 + 共有成分(交集)+ 独有成分(差集)
    """
    # 解析 id 列表(去重,保持顺序)
    try:
        seen_ids: set[int] = set()
        id_list: list[int] = []
        for x in ids.split(","):
            x = x.strip()
            if not x:
                continue
            hid = int(x)
            if hid not in seen_ids:
                seen_ids.add(hid)
                id_list.append(hid)
    except ValueError:
        raise HTTPException(status_code=400, detail="ids 参数格式错误,应为逗号分隔的数字")

    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="至少需要选择 2 条记录进行对比")
    if len(id_list) > 5:
        raise HTTPException(status_code=400, detail="最多支持 5 条记录对比")

    # 查询每条记录的详情
    items: list[CompareItem] = []
    ingredient_sets: dict[int, set[str]] = {}

    for hid in id_list:
        detail = get_history_detail(hid)
        if not detail:
            raise HTTPException(status_code=404, detail=f"历史记录 id={hid} 不存在")

        # 解析完整分析结果
        try:
            result = json.loads(detail["result_json"])
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=f"记录 id={hid} 数据损坏")

        names = [ing["name"] for ing in result.get("ingredients", [])]
        items.append(CompareItem(
            id=hid,
            product_type=result.get("product_type") or detail["product_type"] or "未知产品",
            score=result.get("score", 0),
            pros=result.get("pros", []),
            cons=result.get("cons", []),
            ingredient_names=names,
        ))
        ingredient_sets[hid] = set(names)

    # 计算共有成分(交集)
    common = set.intersection(*ingredient_sets.values()) if ingredient_sets else set()

    # 计算独有成分(每个产品有,但其他产品没有的)
    unique: dict[int, list[str]] = {}
    for hid, names in ingredient_sets.items():
        # 该产品的成分 - 其他所有产品的成分并集
        others = set.union(*[s for i, s in ingredient_sets.items() if i != hid])
        unique[hid] = sorted(names - others)

    return CompareResponse(
        items=items,
        common_ingredients=sorted(common),
        unique_ingredients=unique,
    )


# ===== PDF 报告导出接口 =====

@router.get("/report/{history_id}")
@limiter.limit("10/minute")
def export_report(request: Request, history_id: int):
    """导出指定历史记录的 PDF 报告(旧接口,基于后端历史记录)

    返回 PDF 文件下载(application/pdf)
    """
    detail = get_history_detail(history_id)
    if not detail:
        raise HTTPException(status_code=404, detail="历史记录不存在")

    try:
        pdf_bytes = generate_report_pdf(
            result_json=detail["result_json"],
            created_at=detail["created_at"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {e}")

    # 文件名:产品类型_成分分析报告_日期.pdf
    product_type = detail["product_type"] or "产品"
    # 中文文件名需要 RFC 5987 编码,避免乱码
    filename = f"{product_type}_成分分析报告.pdf"
    encoded_filename = quote(filename)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.post("/report/generate")
@limiter.limit("10/minute")
def generate_report_from_data(request: Request, payload: dict):
    """根据前端传入的完整分析数据生成 PDF 报告(新接口)

    前端历史记录改为 localStorage 后,不再有后端 history_id,
    改为前端 POST 完整 AnalysisResponse 数据,后端直接生成 PDF。

    请求体:AnalysisResponse 的 JSON(含 ocr_text, ingredients, pros, cons,
            score, summary, product_type, interactions, allergen_alerts, alternatives)
    """
    if not payload:
        raise HTTPException(status_code=400, detail="请求体为空")

    result_json = json.dumps(payload, ensure_ascii=False)
    created_at = payload.get("created_at")  # 前端可选传入分析时间

    try:
        pdf_bytes = generate_report_pdf(
            result_json=result_json,
            created_at=created_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {e}")

    product_type = payload.get("product_type") or "产品"
    filename = f"{product_type}_成分分析报告.pdf"
    encoded_filename = quote(filename)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


# ===== 成分库检索接口 =====

@router.get("/ingredients/search", response_model=IngredientSearchResponse)
@limiter.limit("30/minute")
def search_ingredient_db(
    request: Request,
    name: str | None = None,
    category: str | None = None,
    risk_level: str | None = None,
    reference: str | None = None,
    limit: int = 100,
):
    """检索成分库(法规检索页用)

    参数均为可选,支持任意组合:
    - name: 成分名模糊匹配(如 "水杨酸")
    - category: 分类精确匹配(如 "防腐剂")
    - risk_level: 风险等级精确匹配(安全/注意/慎用/规避)
    - reference: 法规出处关键词模糊匹配(如 "安全技术规范")
    - limit: 返回上限(默认 100,最大 500)

    返回:命中成分列表 + 全部分类(供前端下拉)
    """
    rows = search_ingredients(
        name=name,
        category=category,
        risk_level=risk_level,
        reference_keyword=reference,
        limit=limit,
    )
    # 转换为模型
    items = [IngredientSearchItem(**r) for r in rows]
    # 一次性返回全部分类(前端首次加载用)
    categories = get_ingredient_categories()

    return IngredientSearchResponse(
        total=len(items),
        items=items,
        categories=categories,
    )


# ===== 过敏原档案接口 =====

@router.get("/allergens", response_model=AllergenListResponse)
def list_allergens():
    """获取用户过敏原档案列表"""
    rows = get_allergens()
    items = [AllergenItem(**r) for r in rows]
    return AllergenListResponse(items=items, total=len(items))


@router.post("/allergens", response_model=AllergenItem)
@limiter.limit("20/minute")
def create_allergen(request: Request, body: dict):
    """添加过敏成分

    请求体: {"ingredient_name": "香精"}
    已存在则忽略,返回已有记录
    """
    name = body.get("ingredient_name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="ingredient_name 不能为空")
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="成分名过长(最多100字符)")
    record = add_allergen(name)
    if not record:
        raise HTTPException(status_code=500, detail="添加失败")
    return AllergenItem(**record)


@router.delete("/allergens/{allergen_id}")
@limiter.limit("20/minute")
def remove_allergen(request: Request, allergen_id: int):
    """删除一条过敏成分"""
    if not delete_allergen(allergen_id):
        raise HTTPException(status_code=404, detail="过敏原记录不存在")
    return {"message": "已删除", "id": allergen_id}
