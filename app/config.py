import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # 应用配置
    APP_ENV: str = Field(default="production", description="运行环境")
    APP_DEBUG: bool = Field(default=False, description="调试模式")
    APP_HOST: str = Field(default="0.0.0.0", description="监听地址")
    APP_PORT: int = Field(default=8000, description="监听端口")
    
    # 数据库配置
    DATABASE_URL: str = Field(default="", description="数据库连接字符串")
    
    # 缓存配置
    CACHE_TTL_SECONDS: int = Field(default=300, description="缓存TTL（秒）")
    CACHE_MAX_SIZE: int = Field(default=500, description="缓存最大条目数")
    
    # AI 配置
    DEEPSEEK_API_KEY: str = Field(default="", description="DeepSeek API Key")
    DEEPSEEK_API_BASE: str = Field(default="https://api.deepseek.com", description="DeepSeek API 地址")
    AI_MAX_RETRIES: int = Field(default=3, description="AI 最大重试次数")
    AI_TIMEOUT_SECONDS: int = Field(default=30, description="AI 超时时间（秒）")
    AI_DAILY_BUDGET: float = Field(default=10.0, description="AI 每日预算（美元）")
    
    # 国际化配置
    DEFAULT_LANGUAGE: str = Field(default="en", description="默认语言")
    SUPPORTED_LANGUAGES: set = {"en", "zh"}
    
    # 管理后台配置
    ADMIN_USERNAME: str = Field(default="admin", description="管理员用户名")
    ADMIN_PASSWORD: str = Field(default="", description="管理员密码")
    
    # CSRF 配置
    CSRF_SECRET_KEY: str = Field(default="", description="CSRF 密钥")
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = Field(default=20, description="默认每页数量")
    MAX_PAGE_SIZE: int = Field(default=100, description="最大每页数量")
    
    # 抓取配置
    FETCH_TIMEOUT: int = Field(default=20, description="抓取超时（秒）")
    FETCH_MAX_RETRIES: int = Field(default=2, description="抓取最大重试次数")
    FETCH_BATCH_SIZE: int = Field(default=4, description="抓取批次大小")
    FETCH_BATCH_DELAY_MIN: float = Field(default=2.0, description="批次最小延迟（秒）")
    FETCH_BATCH_DELAY_MAX: float = Field(default=5.0, description="批次最大延迟（秒）")
    
    # 去重配置
    DEDUP_THRESHOLD: float = Field(default=0.75, description="去重相似度阈值")
    DEDUP_TITLE_LIMIT: int = Field(default=500, description="去重标题加载数量")
    
    # 关系配置
    RELATION_THRESHOLD: float = Field(default=0.3, description="关系阈值")
    
    # 翻译配置
    TRANSLATION_CACHE_SIZE: int = Field(default=1000, description="翻译缓存大小")
    TRANSLATION_TIMEOUT: int = Field(default=15, description="翻译超时（秒）")
    
    # 事件追踪配置
    EVENT_CACHE_SIZE: int = Field(default=1000, description="事件缓存大小")
    EVENT_MAX_ARTICLES: int = Field(default=20, description="事件最大文章数")
    
    # 图表配置
    CHART_DEFAULT_DAYS: int = Field(default=30, description="图表默认天数")
    CHART_MAX_DAYS: int = Field(default=90, description="图表最大天数")
    
    # 速率限制配置
    RATE_LIMIT_DEFAULT: str = Field(default="60/minute", description="默认速率限制")
    RATE_LIMIT_API: str = Field(default="30/minute", description="API 速率限制")
    RATE_LIMIT_ADMIN: str = Field(default="120/minute", description="管理后台速率限制")
    
    # 分类配置
    USE_LLM_CLASSIFIER: bool = Field(default=True, description="使用 LLM 分类器")
    
    # NER 配置
    USE_NER: bool = Field(default=True, description="使用 NER")
    
    # 去重配置
    USE_TFIDF_DEDUP: bool = Field(default=True, description="使用 TF-IDF 去重")
    
    # 深度分析模块开关
    ENABLE_DEEP_ANALYST: bool = Field(default=False, description="启用深度分析模块")

    # 深度分析流水线配置
    DEEP_ANALYSIS_MAX_EVENTS: int = Field(default=10, description="深度分析最大事件数")
    DEEP_ANALYSIS_COOLDOWN_HOURS: int = Field(default=24, description="深度分析冷却时间（小时）")
    
    # 数据质量配置
    AI_CONFIDENCE_THRESHOLD: float = Field(default=0.7, description="AI 置信度阈值")
    AI_CONFIDENCE_ENABLED: bool = Field(default=True, description="启用 AI 置信度检查")
    AI_RETRY_MAX_RETRIES: int = Field(default=3, description="AI 重试最大次数")
    AI_RETRY_BASE_DELAY: int = Field(default=60, description="AI 重试基础延迟（秒）")
    AI_VERSION_KEEP_COUNT: int = Field(default=5, description="AI 版本保留数量")
    
    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_FILE: Optional[str] = Field(default=None, description="日志文件路径")
    
    # 其他配置
    MYMEMORY_EMAIL: Optional[str] = Field(default=None, description="MyMemory 翻译邮箱")
    MAX_RETRIES: int = Field(default=2, description="最大重试次数")
    RETENTION_DAYS: int = Field(default=365, description="数据保留天数")

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
