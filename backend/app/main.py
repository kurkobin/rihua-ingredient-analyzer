"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.config import settings
from app.limiter import limiter

app = FastAPI(
    title="成分分析 API",
    description="扫描商品配料表,分析产品优缺点",
    version="0.1.0",
)

# 挂载限流器
app.state.limiter = limiter
# 自定义 429 响应:返回中文提示
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429,
        content={"detail": "请求过于频繁,请稍后再试(每分钟限 5 次)"},
    ),
)

# MVP 阶段允许所有来源,生产环境需收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "ingredient-analyzer"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
