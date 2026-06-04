"""
失败分析任务重试管理器

功能：
1. 查询待重试任务
2. 执行重试
3. 更新任务状态
4. 统计信息
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import async_session
from models.failed_task import FailedAnalysisTask
from app.config import settings

logger = logging.getLogger(__name__)


class RetryManager:
    """失败任务重试管理器"""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self._running = False
    
    async def get_pending_tasks(self, limit: int = 10) -> List[FailedAnalysisTask]:
        """
        获取待重试的任务
        
        Args:
            limit: 最大返回数量
        
        Returns:
            待重试任务列表
        """
        async with async_session() as session:
            now = datetime.utcnow()
            query = (
                select(FailedAnalysisTask)
                .where(
                    and_(
                        FailedAnalysisTask.status.in_(["pending", "retrying"]),
                        FailedAnalysisTask.next_retry_at <= now,
                        FailedAnalysisTask.retry_count < FailedAnalysisTask.max_retries
                    )
                )
                .order_by(FailedAnalysisTask.next_retry_at.asc())
                .limit(limit)
            )
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_task_by_id(self, task_id: int) -> Optional[FailedAnalysisTask]:
        """根据ID获取任务"""
        async with async_session() as session:
            return await session.get(FailedAnalysisTask, task_id)
    
    async def get_tasks_by_type(self, task_type: str, status: str = None, 
                                limit: int = 50) -> List[FailedAnalysisTask]:
        """根据类型获取任务"""
        async with async_session() as session:
            query = select(FailedAnalysisTask).where(
                FailedAnalysisTask.task_type == task_type
            )
            
            if status:
                query = query.where(FailedAnalysisTask.status == status)
            
            query = query.order_by(FailedAnalysisTask.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_tasks_by_target(self, target_type: str, target_id: str) -> List[FailedAnalysisTask]:
        """根据目标获取任务"""
        async with async_session() as session:
            query = (
                select(FailedAnalysisTask)
                .where(
                    and_(
                        FailedAnalysisTask.target_type == target_type,
                        FailedAnalysisTask.target_id == target_id
                    )
                )
                .order_by(FailedAnalysisTask.created_at.desc())
            )
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def update_task_status(self, task_id: int, status: str, 
                                 error_message: str = None) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            error_message: 错误消息（可选）
        
        Returns:
            是否更新成功
        """
        async with async_session() as session:
            task = await session.get(FailedAnalysisTask, task_id)
            if not task:
                return False
            
            task.status = status
            task.last_retry_at = datetime.utcnow()
            
            if status == "resolved":
                task.resolved_at = datetime.utcnow()
            
            if error_message:
                task.error_message = error_message
            
            # 计算下次重试时间（指数退避）
            if status == "retrying":
                delay = settings.AI_RETRY_BASE_DELAY * (2 ** task.retry_count)
                task.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
            
            await session.commit()
            return True
    
    async def increment_retry_count(self, task_id: int) -> bool:
        """增加重试次数"""
        async with async_session() as session:
            task = await session.get(FailedAnalysisTask, task_id)
            if not task:
                return False
            
            task.retry_count += 1
            task.last_retry_at = datetime.utcnow()
            
            # 检查是否超过最大重试次数
            if task.retry_count >= task.max_retries:
                task.status = "abandoned"
            else:
                # 计算下次重试时间（指数退避）
                delay = settings.AI_RETRY_BASE_DELAY * (2 ** task.retry_count)
                task.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
            
            await session.commit()
            return True
    
    async def mark_as_resolved(self, task_id: int) -> bool:
        """标记任务为已解决"""
        return await self.update_task_status(task_id, "resolved")
    
    async def mark_as_abandoned(self, task_id: int, reason: str = None) -> bool:
        """标记任务为已放弃"""
        return await self.update_task_status(task_id, "abandoned", reason)
    
    async def create_task(self, task_type: str, target_id: str, input_data: dict,
                         failure_reason: str, error_message: str = None,
                         error_details: dict = None, target_type: str = None) -> Optional[FailedAnalysisTask]:
        """
        创建新的失败任务记录
        
        Args:
            task_type: 任务类型
            target_id: 目标ID
            input_data: 输入数据
            failure_reason: 失败原因
            error_message: 错误消息
            error_details: 错误详情
            target_type: 目标类型
        
        Returns:
            创建的任务或None
        """
        async with async_session() as session:
            # 检查是否已存在相同任务
            existing = await session.execute(
                select(FailedAnalysisTask).where(
                    and_(
                        FailedAnalysisTask.task_type == task_type,
                        FailedAnalysisTask.target_id == target_id,
                        FailedAnalysisTask.status.in_(["pending", "retrying"])
                    )
                )
            )
            existing_task = existing.scalar_one_or_none()
            
            if existing_task:
                # 更新现有任务
                existing_task.retry_count += 1
                existing_task.last_retry_at = datetime.utcnow()
                existing_task.error_message = error_message
                existing_task.error_details = error_details
                
                if existing_task.retry_count >= existing_task.max_retries:
                    existing_task.status = "abandoned"
                else:
                    delay = settings.AI_RETRY_BASE_DELAY * (2 ** existing_task.retry_count)
                    existing_task.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                
                await session.commit()
                return existing_task
            else:
                # 创建新任务
                task = FailedAnalysisTask(
                    task_type=task_type,
                    target_id=target_id,
                    target_type=target_type,
                    input_data=input_data,
                    failure_reason=failure_reason,
                    error_message=error_message,
                    error_details=error_details,
                    next_retry_at=datetime.utcnow() + timedelta(seconds=settings.AI_RETRY_BASE_DELAY)
                )
                session.add(task)
                await session.commit()
                return task
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        获取失败任务统计信息
        
        Returns:
            统计信息字典
        """
        async with async_session() as session:
            # 总任务数
            total_query = select(func.count(FailedAnalysisTask.id))
            total_result = await session.execute(total_query)
            total_count = total_result.scalar()
            
            # 按状态统计
            status_query = (
                select(FailedAnalysisTask.status, func.count(FailedAnalysisTask.id))
                .group_by(FailedAnalysisTask.status)
            )
            status_result = await session.execute(status_query)
            status_stats = {row[0]: row[1] for row in status_result.fetchall()}
            
            # 按类型统计
            type_query = (
                select(FailedAnalysisTask.task_type, func.count(FailedAnalysisTask.id))
                .group_by(FailedAnalysisTask.task_type)
            )
            type_result = await session.execute(type_query)
            type_stats = {row[0]: row[1] for row in type_result.fetchall()}
            
            # 按失败原因统计
            reason_query = (
                select(FailedAnalysisTask.failure_reason, func.count(FailedAnalysisTask.id))
                .where(FailedAnalysisTask.failure_reason.isnot(None))
                .group_by(FailedAnalysisTask.failure_reason)
            )
            reason_result = await session.execute(reason_query)
            reason_stats = {row[0]: row[1] for row in reason_result.fetchall()}
            
            # 待重试任务数
            pending_query = (
                select(func.count(FailedAnalysisTask.id))
                .where(
                    and_(
                        FailedAnalysisTask.status.in_(["pending", "retrying"]),
                        FailedAnalysisTask.retry_count < FailedAnalysisTask.max_retries
                    )
                )
            )
            pending_result = await session.execute(pending_query)
            pending_count = pending_result.scalar()
            
            return {
                "total": total_count,
                "by_status": status_stats,
                "by_type": type_stats,
                "by_reason": reason_stats,
                "pending_retry": pending_count
            }
    
    async def cleanup_old_tasks(self, days: int = 30) -> int:
        """
        清理旧的已完成/已放弃任务
        
        Args:
            days: 保留天数
        
        Returns:
            删除的任务数
        """
        async with async_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # 删除已完成或已放弃的旧任务
            delete_query = (
                FailedAnalysisTask.__table__.delete()
                .where(
                    and_(
                        FailedAnalysisTask.status.in_(["resolved", "abandoned"]),
                        FailedAnalysisTask.created_at < cutoff_date
                    )
                )
            )
            
            result = await session.execute(delete_query)
            await session.commit()
            
            return result.rowcount


# 全局实例
retry_manager = RetryManager()


def get_retry_manager() -> RetryManager:
    """获取重试管理器实例"""
    return retry_manager
