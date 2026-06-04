from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Integer, Float, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class AnalysisVersion(Base):
    """分析结果版本历史"""
    __tablename__ = "analysis_versions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 版本标识
    version_number = Column(Integer, nullable=False)
    analysis_type = Column(String(50), nullable=False)  # article, knowledge, causal, scenario, daily_report
    target_id = Column(String(200), nullable=False)  # 目标ID
    
    # 分析结果快照
    result_data = Column(JSONB, nullable=False)
    
    # 置信度
    confidence = Column(Float)
    
    # 变更信息
    change_summary = Column(Text)
    changed_fields = Column(JSONB)  # ["sentiment", "summary_zh"]
    previous_version_id = Column(BigInteger, ForeignKey("analysis_versions.id"))
    
    # 元数据
    ai_model = Column(String(50))
    analysis_duration_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("analysis_type", "target_id", "version_number", name="uq_analysis_version"),
    )

    def __repr__(self):
        return f"<AnalysisVersion(id={self.id}, type={self.analysis_type}, target={self.target_id}, v{self.version_number})>"

    @property
    def version_label(self):
        """版本标签"""
        return f"v{self.version_number}"

    def diff_with(self, other_version: 'AnalysisVersion') -> dict:
        """与另一个版本对比"""
        if self.analysis_type != other_version.analysis_type:
            raise ValueError("Cannot compare versions of different analysis types")
        
        changes = {}
        old_data = self.result_data or {}
        new_data = other_version.result_data or {}
        
        # 获取所有字段
        all_keys = set(old_data.keys()) | set(new_data.keys())
        
        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            
            if old_val != new_val:
                changes[key] = {
                    "old": old_val,
                    "new": new_val
                }
        
        return changes
