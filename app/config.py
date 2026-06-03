import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # 应用配置
    APP_ENV: str = os.getenv("APP_ENV", "production")
    APP_DEBUG: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    
    # 数据库配置
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # 缓存配置
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    CACHE_MAX_SIZE: int = int(os.getenv("CACHE_MAX_SIZE", "100"))
    
    # AI 配置
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE: str = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    AI_MAX_RETRIES: int = int(os.getenv("AI_MAX_RETRIES", "3"))
    AI_TIMEOUT_SECONDS: int = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
    AI_DAILY_BUDGET: float = float(os.getenv("AI_DAILY_BUDGET", "10.0"))
    
    # 国际化配置
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "en")
    SUPPORTED_LANGUAGES: set = {"en", "zh"}
    
    # 管理后台配置
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    
    # CSRF 配置
    CSRF_SECRET_KEY: str = os.getenv("CSRF_SECRET_KEY", "")
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))
    MAX_PAGE_SIZE: int = int(os.getenv("MAX_PAGE_SIZE", "100"))
    
    # 抓取配置
    FETCH_TIMEOUT: int = int(os.getenv("FETCH_TIMEOUT", "20"))
    FETCH_MAX_RETRIES: int = int(os.getenv("FETCH_MAX_RETRIES", "2"))
    FETCH_BATCH_SIZE: int = int(os.getenv("FETCH_BATCH_SIZE", "4"))
    FETCH_BATCH_DELAY_MIN: float = float(os.getenv("FETCH_BATCH_DELAY_MIN", "2.0"))
    FETCH_BATCH_DELAY_MAX: float = float(os.getenv("FETCH_BATCH_DELAY_MAX", "5.0"))
    
    # 去重配置
    DEDUP_THRESHOLD: float = float(os.getenv("DEDUP_THRESHOLD", "0.75"))
    DEDUP_TITLE_LIMIT: int = int(os.getenv("DEDUP_TITLE_LIMIT", "500"))
    
    # 关系配置
    RELATION_THRESHOLD: float = float(os.getenv("RELATION_THRESHOLD", "0.3"))
    
    # 翻译配置
    TRANSLATION_CACHE_SIZE: int = int(os.getenv("TRANSLATION_CACHE_SIZE", "1000"))
    TRANSLATION_TIMEOUT: int = int(os.getenv("TRANSLATION_TIMEOUT", "15"))
    
    # 事件追踪配置
    EVENT_CACHE_SIZE: int = int(os.getenv("EVENT_CACHE_SIZE", "1000"))
    EVENT_MAX_ARTICLES: int = int(os.getenv("EVENT_MAX_ARTICLES", "20"))
    
    # 图表配置
    CHART_DEFAULT_DAYS: int = int(os.getenv("CHART_DEFAULT_DAYS", "30"))
    CHART_MAX_DAYS: int = int(os.getenv("CHART_MAX_DAYS", "90"))


settings = Settings()
