"""应用配置:从环境变量读取,不硬编码任何密钥。

密钥来源(按优先级):
1. 进程环境变量(os.environ)
2. Windows 用户注册表环境变量(旧终端会话兜底)

实际使用的环境变量名:
- DEEPSEEK_API_KEY
- BAIDU_API_KEY
- BAIDU_Secret_Key
"""
import os
import sys

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

def _load_env_from_registry() -> None:
    """Windows: 若进程环境变量缺失(旧终端会话),从用户注册表补充。

    只补充 os.environ 中不存在的变量,不覆盖已有值。
    非 Windows 环境直接跳过。
    """
    if sys.platform != "win32":
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    if name not in os.environ and isinstance(value, str):
                        os.environ[name] = value
                    i += 1
                except OSError:
                    break
    except Exception:
        # 注册表读取失败不阻断启动,后续会因密钥缺失给出明确提示
        pass

# 模块导入时执行,确保旧终端也能拿到用户级环境变量
_load_env_from_registry()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    # DeepSeek(环境变量 DEEPSEEK_API_KEY)
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # 百度云 OCR(环境变量 BAIDU_API_KEY / BAIDU_Secret_Key)
    baidu_api_key: str = Field(default="", validation_alias="BAIDU_API_KEY")
    baidu_secret_key: str = Field(default="", validation_alias="BAIDU_Secret_Key")

    # 应用
    app_host: str = "127.0.0.1"
    app_port: int = 8000

settings = Settings()
