"""
共享 AI 客户端模块
提供基础的 DeepSeek API 调用功能
"""

import asyncio
import hashlib
import json
import logging
from typing import Optional

from app.ai_metrics import get_ai_metrics
from app.config import settings

logger = logging.getLogger(__name__)

# AI 调用结果缓存实例（独立于应用层缓存）
_ai_cache = None


def _get_ai_cache():
    """懒加载 AI 缓存实例"""
    global _ai_cache
    if _ai_cache is None and settings.AI_CACHE_ENABLED:
        from app.cache import PerItemTTLCache
        _ai_cache = PerItemTTLCache(
            maxsize=settings.AI_CACHE_MAX_SIZE,
            default_ttl=settings.AI_CACHE_TTL,
        )
    return _ai_cache


def get_ai_cache_stats() -> dict:
    """获取 AI 缓存统计信息"""
    cache = _get_ai_cache()
    if cache:
        return cache.get_stats()
    return {"enabled": False}


def _make_cache_key(function_name: str, messages: list[dict], model: str) -> str:
    """生成 AI 调用的缓存 key"""
    # 取 messages 的核心内容做 hash（忽略 role 顺序等细微差异）
    content = json.dumps(messages, sort_keys=True, ensure_ascii=False)
    msg_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:16]
    return f"ai:{function_name}:{model}:{msg_hash}"


class BaseDeepSeekClient:
    """
    DeepSeek API 基础客户端
    提供通用的 API 调用和重试机制
    """
    
    # 可重试的异常类型
    RETRYABLE_ERRORS = (
        "RateLimitError",
        "APITimeoutError", 
        "APIConnectionError",
        "APIStatusError",
    )
    
    def __init__(self, max_retries: int = None, timeout: int = None):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.api_base = settings.DEEPSEEK_API_BASE
        self.enabled = bool(self.api_key)
        self.max_retries = max_retries or settings.AI_MAX_RETRIES
        self.timeout = timeout or settings.AI_TIMEOUT_SECONDS
        
        if not self.enabled:
            logger.info("DeepSeek API: 未配置 API Key，AI 分析功能已禁用")
            self.client = None
            return
        
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
                timeout=self.timeout
            )
            logger.info(f"DeepSeek API: 已连接 {self.api_base}")
        except ImportError:
            logger.warning("openai 包未安装，无法使用 AI 分析功能")
            self.enabled = False
            self.client = None
    
    async def _call_api(self, messages: list[dict], temperature: float = 0.7, 
                  max_tokens: int = 2000, function_name: str = "unknown",
                  model: str = None) -> Optional[str]:
        """
        调用 API（带重试机制、指标监控和结果缓存）
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            function_name: 调用函数名（用于指标统计）
            model: 模型名称，为空时使用默认 deepseek-chat
        
        Returns:
            API 响应内容或 None
        """
        if not self.enabled or not self.client:
            return None
        
        resolved_model = model or "deepseek-chat"
        metrics = get_ai_metrics()
        
        # 检查缓存（仅对低 temperature 调用缓存，结果确定性高）
        ai_cache = _get_ai_cache()
        if ai_cache and temperature <= 0.5:
            cache_key = _make_cache_key(function_name, messages, resolved_model)
            cached = ai_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"AI 缓存命中: {function_name}")
                return cached
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.timeout
                )
                
                # 记录 token 使用量
                if hasattr(response, 'usage') and response.usage:
                    usage = response.usage
                    metrics.record_usage(
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        function_name=function_name
                    )
                    logger.debug(f"API 调用: prompt={usage.prompt_tokens}, "
                               f"completion={usage.completion_tokens}, "
                               f"total={usage.total_tokens}")
                
                result = response.choices[0].message.content
                
                # 写入缓存
                if ai_cache and temperature <= 0.5:
                    cache_key = _make_cache_key(function_name, messages, resolved_model)
                    ai_cache.set(cache_key, result)
                
                return result
                
            except Exception as e:
                error_type = type(e).__name__
                last_error = e
                
                # 检查是否为可重试错误
                if error_type in self.RETRYABLE_ERRORS:
                    wait_time = (2 ** attempt) * 1.0  # 指数退避
                    logger.warning(f"API 调用失败 ({error_type}), {wait_time}s 后重试 "
                                 f"(第{attempt + 1}/{self.max_retries}次): {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # 不可重试错误，直接失败
                    logger.error(f"API 调用异常 ({error_type}): {e}")
                    metrics.record_error(function_name)
                    return None
        
        # 所有重试都失败
        logger.error(f"API 调用失败，已重试{self.max_retries}次: {last_error}")
        metrics.record_error(function_name)
        return None
    
    async def chat(self, messages: list[dict], temperature: float = 0.7, 
             max_tokens: int = 2000, function_name: str = "chat",
             model: str = None) -> Optional[str]:
        """
        公共 API 调用接口
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            function_name: 调用函数名（用于指标统计）
            model: 模型名称，为空时使用默认 deepseek-chat
        
        Returns:
            API 响应内容或 None
        """
        return await self._call_api(messages, temperature, max_tokens, function_name, model)
