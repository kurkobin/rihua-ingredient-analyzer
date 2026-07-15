"""百度云文字识别(OCR)服务

使用通用文字识别(高精度版),每月 1000 次免费额度。
文档:https://cloud.baidu.com/doc/OCR/s/Ck3h7y2ia
"""
import asyncio
import base64
import time

import httpx

from app.config import settings
from app.logger import logger
from app.models.schemas import OCRResult

# 重试配置
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # 基础延迟(秒),实际延迟 = base * 2^attempt


class BaiduOCRService:
    """百度云 OCR 服务"""

    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    # 高精度版接口
    OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"

    def __init__(self):
        self.api_key = settings.baidu_api_key
        self.secret_key = settings.baidu_secret_key
        # access_token 缓存(token 有效期 30 天)
        self._access_token: str | None = None
        self._token_expire_at: float = 0

    async def _get_access_token(self) -> str:
        """获取百度云 access_token(带缓存)"""
        if self._access_token and time.time() < self._token_expire_at:
            return self._access_token

        if not self.api_key or not self.secret_key:
            raise RuntimeError(
                "百度云 OCR 密钥未配置,请在系统环境变量中设置 BAIDU_API_KEY 和 BAIDU_Secret_Key"
            )

        logger.info("正在获取百度云 access_token...")
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            resp = await client.post(self.TOKEN_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data.get("access_token", "")
        # expires_in 单位秒,提前 60 秒过期以留余量
        expires_in = data.get("expires_in", 2592000)
        self._token_expire_at = time.time() + expires_in - 60
        logger.info("百度云 access_token 获取成功")
        return self._access_token

    async def recognize(self, image_bytes: bytes) -> OCRResult:
        """识别图片中的文字(带重试机制)

        Args:
            image_bytes: 图片二进制数据

        Returns:
            OCRResult: 识别出的文字
        """
        start_time = time.time()
        image_size_kb = len(image_bytes) / 1024
        logger.info(f"开始 OCR 识别,图片大小: {image_size_kb:.1f} KB")

        token = await self._get_access_token()

        # 百度云要求 base64 编码,且图片不超过 10MB
        image_b64 = base64.b64encode(image_bytes).decode()
        params = {"image": image_b64}

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                # 大图片上传较慢,超时设为 60 秒
                async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                    resp = await client.post(
                        f"{self.OCR_URL}?access_token={token}",
                        data=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                # 检查错误
                if "error_code" in data:
                    error_msg = f"百度云 OCR 错误 [{data['error_code']}]: {data.get('error_msg', '未知错误')}"
                    logger.warning(f"OCR 第 {attempt + 1} 次尝试失败: {error_msg}")
                    last_error = RuntimeError(error_msg)
                    # 业务错误(如图片格式问题)不重试
                    if data["error_code"] in (216200, 216201, 216202):
                        raise last_error
                else:
                    # 成功
                    words_result = data.get("words_result") or []
                    words = [item["words"] for item in words_result]
                    text = "\n".join(words)
                    elapsed = time.time() - start_time
                    logger.info(f"OCR 识别成功,识别到 {len(words)} 行文字,耗时 {elapsed:.2f}s")
                    return OCRResult(text=text, words=words)

            except httpx.HTTPError as e:
                # 网络错误,可重试
                last_error = e
                logger.warning(f"OCR 第 {attempt + 1} 次网络错误: {type(e).__name__}: {e}")

            # 指数退避等待(最后一次不等待)
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.info(f"等待 {delay}s 后重试...")
                await asyncio.sleep(delay)

        # 所有重试都失败
        elapsed = time.time() - start_time
        logger.error(f"OCR 识别彻底失败,重试 {MAX_RETRIES} 次后仍报错,总耗时 {elapsed:.2f}s")
        raise RuntimeError(f"OCR 识别失败(重试 {MAX_RETRIES} 次): {last_error}")
