"""
分析结果版本管理器

功能：
1. 保存分析结果版本
2. 版本历史查询
3. 版本对比
4. 自动清理旧版本
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import async_session
from models.analysis_version import AnalysisVersion
from app.config import settings

logger = logging.getLogger(__name__)


class VersionManager:
    """分析结果版本管理器"""
    
    async def save_version(
        self,
        analysis_type: str,
        target_id: str,
        result_data: dict,
        confidence: float = None,
        ai_model: str = None,
        analysis_duration_ms: int = None,
        change_summary: str = None,
    ) -> Optional[AnalysisVersion]:
        """
        保存分析结果版本
        
        Args:
            analysis_type: 分析类型 (article, knowledge, causal, scenario, daily_report)
            target_id: 目标ID
            result_data: 分析结果数据
            confidence: 置信度
            ai_model: AI模型名称
            analysis_duration_ms: 分析耗时（毫秒）
            change_summary: 变更摘要
        
        Returns:
            保存的版本对象或None
        """
        async with async_session() as session:
            # 获取当前最新版本号
            latest_query = (
                select(func.max(AnalysisVersion.version_number))
                .where(
                    AnalysisVersion.analysis_type == analysis_type,
                    AnalysisVersion.target_id == target_id,
                )
            )
            latest_result = await session.execute(latest_query)
            latest_version = latest_result.scalar() or 0
            
            new_version_number = latest_version + 1
            
            # 计算变更字段
            changed_fields = None
            if latest_version > 0:
                previous_query = (
                    select(AnalysisVersion)
                    .where(
                        AnalysisVersion.analysis_type == analysis_type,
                        AnalysisVersion.target_id == target_id,
                        AnalysisVersion.version_number == latest_version,
                    )
                )
                previous_result = await session.execute(previous_query)
                previous_version = previous_result.scalar_one_or_none()
                
                if previous_version:
                    changed_fields = self._calculate_changed_fields(
                        previous_version.result_data, result_data
                    )
            
            # 创建新版本
            version = AnalysisVersion(
                version_number=new_version_number,
                analysis_type=analysis_type,
                target_id=target_id,
                result_data=result_data,
                confidence=confidence,
                change_summary=change_summary or self._generate_change_summary(changed_fields),
                changed_fields=changed_fields,
                ai_model=ai_model,
                analysis_duration_ms=analysis_duration_ms,
            )
            
            session.add(version)
            await session.commit()
            
            # 清理旧版本
            await self._cleanup_old_versions(session, analysis_type, target_id)
            
            logger.info(f"保存分析版本: {analysis_type}/{target_id} v{new_version_number}")
            return version
    
    async def get_version(
        self,
        analysis_type: str,
        target_id: str,
        version_number: int,
    ) -> Optional[AnalysisVersion]:
        """获取指定版本"""
        async with async_session() as session:
            query = select(AnalysisVersion).where(
                AnalysisVersion.analysis_type == analysis_type,
                AnalysisVersion.target_id == target_id,
                AnalysisVersion.version_number == version_number,
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def get_latest_version(
        self,
        analysis_type: str,
        target_id: str,
    ) -> Optional[AnalysisVersion]:
        """获取最新版本"""
        async with async_session() as session:
            query = (
                select(AnalysisVersion)
                .where(
                    AnalysisVersion.analysis_type == analysis_type,
                    AnalysisVersion.target_id == target_id,
                )
                .order_by(AnalysisVersion.version_number.desc())
                .limit(1)
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def get_version_history(
        self,
        analysis_type: str,
        target_id: str,
        limit: int = 10,
    ) -> List[AnalysisVersion]:
        """获取版本历史"""
        async with async_session() as session:
            query = (
                select(AnalysisVersion)
                .where(
                    AnalysisVersion.analysis_type == analysis_type,
                    AnalysisVersion.target_id == target_id,
                )
                .order_by(AnalysisVersion.version_number.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            return result.scalars().all()
    
    async def compare_versions(
        self,
        analysis_type: str,
        target_id: str,
        version1: int,
        version2: int,
    ) -> Dict[str, Any]:
        """
        对比两个版本
        
        Args:
            analysis_type: 分析类型
            target_id: 目标ID
            version1: 第一个版本号
            version2: 第二个版本号
        
        Returns:
            对比结果字典
        """
        v1 = await self.get_version(analysis_type, target_id, version1)
        v2 = await self.get_version(analysis_type, target_id, version2)
        
        if not v1 or not v2:
            raise ValueError("版本不存在")
        
        changes = v1.diff_with(v2)
        
        return {
            "analysis_type": analysis_type,
            "target_id": target_id,
            "version1": {
                "version_number": v1.version_number,
                "confidence": v1.confidence,
                "created_at": v1.created_at.isoformat() if v1.created_at else None,
            },
            "version2": {
                "version_number": v2.version_number,
                "confidence": v2.confidence,
                "created_at": v2.created_at.isoformat() if v2.created_at else None,
            },
            "changes": changes,
            "changed_fields": list(changes.keys()),
            "total_changes": len(changes),
        }
    
    def _calculate_changed_fields(self, old_data: dict, new_data: dict) -> List[str]:
        """计算变更字段列表"""
        if not old_data or not new_data:
            return []
        
        changed = []
        all_keys = set(old_data.keys()) | set(new_data.keys())
        
        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            
            if old_val != new_val:
                changed.append(key)
        
        return changed
    
    def _generate_change_summary(self, changed_fields: List[str]) -> str:
        """生成变更摘要"""
        if not changed_fields:
            return "无变更"
        
        field_names = {
            "sentiment": "情感",
            "sentiment_score": "情感分数",
            "summary_zh": "中文摘要",
            "key_points": "关键要点",
            "tags": "标签",
            "importance": "重要性",
            "overview": "概述",
            "hot_topics": "热门话题",
            "market_sentiment": "市场情绪",
            "key_events": "关键事件",
            "trend_analysis": "趋势分析",
        }
        
        changed_names = [field_names.get(f, f) for f in changed_fields[:5]]
        summary = f"更新了 {', '.join(changed_names)}"
        
        if len(changed_fields) > 5:
            summary += f" 等 {len(changed_fields)} 个字段"
        
        return summary
    
    async def _cleanup_old_versions(
        self,
        session: AsyncSession,
        analysis_type: str,
        target_id: str,
    ):
        """清理旧版本，保留最近N个"""
        keep_count = settings.AI_VERSION_KEEP_COUNT
        
        # 获取需要删除的版本
        subquery = (
            select(AnalysisVersion.id)
            .where(
                AnalysisVersion.analysis_type == analysis_type,
                AnalysisVersion.target_id == target_id,
            )
            .order_by(AnalysisVersion.version_number.desc())
            .offset(keep_count)
        )
        
        # 删除旧版本
        delete_query = (
            delete(AnalysisVersion)
            .where(AnalysisVersion.id.in_(subquery))
        )
        
        result = await session.execute(delete_query)
        if result.rowcount > 0:
            logger.info(f"清理了 {result.rowcount} 个旧版本: {analysis_type}/{target_id}")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取版本统计信息"""
        async with async_session() as session:
            # 总版本数
            total_query = select(func.count(AnalysisVersion.id))
            total_result = await session.execute(total_query)
            total_count = total_result.scalar()
            
            # 按分析类型统计
            type_query = (
                select(AnalysisVersion.analysis_type, func.count(AnalysisVersion.id))
                .group_by(AnalysisVersion.analysis_type)
            )
            type_result = await session.execute(type_query)
            type_stats = {row[0]: row[1] for row in type_result.fetchall()}
            
            # 平均版本数
            avg_query = select(
                AnalysisVersion.analysis_type,
                AnalysisVersion.target_id,
                func.count(AnalysisVersion.id).label("version_count")
            ).group_by(
                AnalysisVersion.analysis_type,
                AnalysisVersion.target_id
            )
            avg_result = await session.execute(avg_query)
            version_counts = [row[2] for row in avg_result.fetchall()]
            avg_versions = sum(version_counts) / len(version_counts) if version_counts else 0
            
            return {
                "total_versions": total_count,
                "by_type": type_stats,
                "avg_versions_per_target": round(avg_versions, 2),
                "total_targets": len(version_counts),
            }


# 全局实例
version_manager = VersionManager()


def get_version_manager() -> VersionManager:
    """获取版本管理器实例"""
    return version_manager
