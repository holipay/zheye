"""
错误消息常量
集中管理 API 错误消息，便于国际化和维护
"""


class ErrorMessages:
    """错误消息常量类"""
    
    # 通用错误
    NOT_FOUND = "Resource not found / 资源未找到"
    INVALID_REQUEST = "Invalid request / 无效请求"
    INTERNAL_ERROR = "Internal server error / 内部服务器错误"
    UNAUTHORIZED = "Unauthorized / 未授权"
    FORBIDDEN = "Forbidden / 禁止访问"
    
    # 认证相关
    AUTH_REQUIRED = "Authentication required / 需要认证"
    AUTH_INVALID = "Invalid credentials / 用户名或密码错误"
    ADMIN_NOT_CONFIGURED = "Admin not configured / 管理后台未配置"
    
    # CSRF 相关
    CSRF_MISSING = "CSRF token missing / CSRF token 缺失"
    CSRF_INVALID = "CSRF token invalid / CSRF token 无效"
    CSRF_NOT_SUBMITTED = "CSRF token not submitted / CSRF token 未提交"
    
    # 新闻相关
    NEWS_NOT_FOUND = "Article not found / 文章未找到"
    
    # 事件相关
    EVENT_NOT_FOUND = "Event not found / 事件未找到"
    
    # 分析相关
    ANALYSIS_NOT_FOUND = "Analysis not found / 分析报告未找到"
    ANALYSIS_VERSION_NOT_FOUND = "Analysis version not found / 未找到分析版本"
    INVALID_DATE_FORMAT = "Invalid date format, use YYYY-MM-DD / 日期格式无效，请使用 YYYY-MM-DD"
    INVALID_REPORT_TYPE = "Invalid report type / 无效的报告类型"
    
    # 任务相关
    TASK_NOT_FOUND = "Task not found / 任务不存在"
    TASK_NOT_RETRYABLE = "Task status not retryable / 任务状态不可重试"
    
    # 源配置相关
    SOURCE_NOT_FOUND = "Source not found / 源未找到"
    SAVE_CONFIG_FAILED = "Failed to save config / 保存配置失败"
    
    # 深度分析相关
    KNOWLEDGE_ANALYSIS_FAILED = "Knowledge analysis failed / 知识分析失败"
    CAUSAL_CHAIN_ANALYSIS_FAILED = "Causal chain analysis failed / 因果链分析失败"
    REPRESENTATION_EXTRACTION_FAILED = "Representation extraction failed / 表征提取失败"
    SCENARIO_ANALYSIS_FAILED = "Scenario analysis failed / 情景分析失败"
    KNOWLEDGE_ATOM_NOT_FOUND = "Knowledge atom not found / 知识原子不存在"