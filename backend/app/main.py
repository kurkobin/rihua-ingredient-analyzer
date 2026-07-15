"""FastAPI 应用入口"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.config import settings
from app.limiter import limiter
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期:启动时初始化成分库(若为空)"""
    # 启动时自动初始化成分库数据(解决容器重启数据丢失问题)
    try:
        seed_if_empty()
    except Exception as e:
        # seed 失败不阻断启动,后续接口会给出明确提示
        print(f"[startup] 成分库初始化失败: {e}")
    yield


app = FastAPI(
    title="成分分析 API",
    description="扫描商品配料表,分析产品优缺点",
    version="0.1.0",
    lifespan=lifespan,
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

# CORS:生产环境收紧为前端域名白名单
# 从环境变量读取,方便将来切换部署平台(如 Cloudflare Pages → 腾讯云)
# 环境变量 CORS_ORIGINS 用逗号分隔多个域名
import os

_default_origins = "http://localhost:5173,http://127.0.0.1:5173,https://rihua-ingredient-analyzer.vercel.app"
_cors_env = os.getenv("CORS_ORIGINS", _default_origins)
allow_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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
