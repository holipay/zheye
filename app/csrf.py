"""
CSRF 保护模块
提供跨站请求伪造保护
"""

import secrets
import hmac
from fastapi import Request, HTTPException, status
from app.config import settings

# CSRF token 有效期（秒）
CSRF_TOKEN_MAX_AGE = 3600  # 1 小时

# 存储 CSRF token 的 cookie 名称
CSRF_COOKIE_NAME = "csrf_token"

# 存储 CSRF token 的 header 名称
CSRF_HEADER_NAME = "X-CSRF-Token"

# 存储 CSRF token 的表单字段名称
CSRF_FORM_FIELD = "csrf_token"


def generate_csrf_token() -> str:
    """生成 CSRF token"""
    return secrets.token_urlsafe(32)


def _get_secret_key() -> str:
    """获取用于签名的密钥"""
    # 使用 ADMIN_PASSWORD 作为密钥，如果没有则使用固定的默认值
    # 注意：在生产环境中应该使用专门的密钥
    return settings.ADMIN_PASSWORD or "default-csrf-secret-key-change-in-production"


def sign_token(token: str) -> str:
    """对 token 进行签名"""
    secret = _get_secret_key()
    signature = hmac.new(secret.encode(), token.encode(), 'sha256').hexdigest()
    return f"{token}.{signature}"


def verify_signed_token(signed_token: str) -> bool:
    """验证签名的 token"""
    try:
        parts = signed_token.split('.', 1)
        if len(parts) != 2:
            return False
        
        token, signature = parts
        secret = _get_secret_key()
        expected_signature = hmac.new(secret.encode(), token.encode(), 'sha256').hexdigest()
        
        # 使用常量时间比较防止时序攻击
        return hmac.compare_digest(signature, expected_signature)
    except Exception:
        return False


def get_csrf_token_from_request(request: Request) -> str:
    """从请求中获取 CSRF token"""
    # 优先从 header 获取
    token = request.headers.get(CSRF_HEADER_NAME)
    if token:
        return token
    
    # 其次从表单数据获取
    # 注意：这需要请求体是表单格式
    return ""


def validate_csrf_token(request: Request) -> bool:
    """验证 CSRF token"""
    # 对于 GET、HEAD、OPTIONS 请求，不需要验证 CSRF
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    
    # 从 cookie 获取存储的 token
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token 缺失"
        )
    
    # 验证 cookie 中的 token 签名
    if not verify_signed_token(cookie_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token 无效"
        )
    
    # 从请求中获取提交的 token
    request_token = get_csrf_token_from_request(request)
    if not request_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token 未提交"
        )
    
    # 验证提交的 token 签名
    if not verify_signed_token(request_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token 无效"
        )
    
    # 使用常量时间比较防止时序攻击
    return hmac.compare_digest(cookie_token, request_token)


async def csrf_protect(request: Request) -> bool:
    """CSRF 保护依赖项"""
    return validate_csrf_token(request)
