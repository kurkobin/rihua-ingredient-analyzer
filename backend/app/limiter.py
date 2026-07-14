"""限流器实例(独立模块,避免 main.py 和 routes.py 循环导入)"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# 按客户端 IP 限流
limiter = Limiter(key_func=get_remote_address)
