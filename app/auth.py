"""
管理后台认证模块
提供 HTTP Basic Auth 认证
"""

import secrets
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.config import settings

security = HTTPBasic(auto_error=False)


def verify_admin_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    """验证管理员凭证"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要认证",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    # 如果未配置密码，拒绝访问
    if not settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="管理后台未配置，请设置 ADMIN_PASSWORD 环境变量",
        )
    
    # 使用常量时间比较防止时序攻击
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.ADMIN_USERNAME.encode("utf-8")
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.ADMIN_PASSWORD.encode("utf-8")
    )
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return True


def check_admin_enabled() -> bool:
    """检查管理后台是否已启用（已配置密码）"""
    if not settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="管理后台未配置",
        )
    return True
