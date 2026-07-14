"""数据模型定义"""
from pydantic import BaseModel


class OCRResult(BaseModel):
    """OCR 识别结果"""
    text: str
    words: list[str] = []


class IngredientInfo(BaseModel):
    """单个成分信息"""
    name: str
    category: str | None = None  # 分类:表面活性剂/防腐剂/...
    risk_level: str | None = None  # 安全/注意/慎用/规避
    description: str | None = None
    in_database: bool = False  # 是否在成分库中
    reference: str | None = None  # 法规/文献出处


class AnalysisResult(BaseModel):
    """LLM 分析结果"""
    pros: list[str] = []
    cons: list[str] = []
    score: int = 0  # 0-100
    summary: str = ""
    product_type: str = ""  # 产品品类(洗发水/牙膏/沐浴露等)


class AnalysisResponse(BaseModel):
    """分析接口返回"""
    ocr_text: str
    ingredients: list[IngredientInfo]
    pros: list[str]
    cons: list[str]
    score: int
    summary: str
    product_type: str = ""  # 产品品类
    history_id: int | None = None  # 历史记录 id(用于导出 PDF)


class HistoryItem(BaseModel):
    """历史记录列表项(不含完整结果,节省传输)"""
    id: int
    img_hash: str
    product_type: str | None = None
    summary: str | None = None
    score: int | None = None
    ingredient_count: int | None = None
    created_at: str


class HistoryDetail(BaseModel):
    """历史记录详情(含完整分析结果)"""
    id: int
    img_hash: str
    product_type: str | None = None
    summary: str | None = None
    score: int | None = None
    ingredient_count: int | None = None
    result_json: str  # 完整 AnalysisResponse JSON
    created_at: str


class CompareItem(BaseModel):
    """对比中的单个产品摘要"""
    id: int
    product_type: str
    score: int
    pros: list[str] = []
    cons: list[str] = []
    ingredient_names: list[str] = []  # 该产品的全部成分名


class CompareResponse(BaseModel):
    """对比接口返回"""
    items: list[CompareItem]  # 各产品摘要
    common_ingredients: list[str] = []  # 共有成分(交集)
    unique_ingredients: dict[int, list[str]] = {}  # 独有成分(按产品 id 分组)


class IngredientSearchItem(BaseModel):
    """成分库检索结果项"""
    id: int
    name: str
    category: str | None = None
    risk_level: str | None = None
    description: str | None = None
    reference: str | None = None


class IngredientSearchResponse(BaseModel):
    """成分库检索接口返回"""
    total: int  # 命中总数
    items: list[IngredientSearchItem]
    categories: list[str] = []  # 全部分类(用于前端下拉)
