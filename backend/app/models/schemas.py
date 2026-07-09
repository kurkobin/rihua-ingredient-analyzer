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
