"""
公共工具模块
从共享模块导入，保持向后兼容
"""

from common.utils import (
    smart_truncate,
    text_similarity,
)

__all__ = [
    "smart_truncate",
    "text_similarity",
]
