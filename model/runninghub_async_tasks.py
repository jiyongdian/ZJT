"""
RunningHub Async Tasks Model - Database operations for runninghub_async_tasks table
RunningHub 异步任务模型 - 支持音频生成等异步任务的轮询状态共享
"""
from typing import List, Optional, Dict, Any
from .database import execute_query, execute_update, execute_insert
import logging

logger = logging.getLogger(__name__)


class RunningHubAsyncTaskStatus:
    """RunningHub 异步任务状态常量"""
    QUEUED = 0          # 队列中（已提交到 RunningHub）
    PROCESSING = 1      # 处理中（正在轮询）
    COMPLETED = 2       # 完成
    FAILED = -1         # 失败
    TIMEOUT = -2        # 超时


class RunningHubAsyncTask:
    """RunningHub 异步任务模型"""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.task_key = kwargs.get('task_key')
        self.runninghub_task_id = kwargs.get('runninghub_task_id')
        self.task_type = kwargs.get('task_type')
        self.user_id = kwargs.get('user_id')
        self.character_id = kwargs.get('character_id')
        self.character_name = kwargs.get('character_name')
        self.style_prompt = kwargs.get('style_prompt')
        self.text = kwargs.get('text')
        self.status = kwargs.get('status', RunningHubAsyncTaskStatus.QUEUED)
        self.try_count = kwargs.get('try_count', 0)
        self.max_attempts = kwargs.get('max_attempts', 60)
        self.error_message = kwargs.get('error_message')
        self.result_url = kwargs.get('result_url')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        self.completed_at = kwargs.get('completed_at')
        self.failed_at = kwargs.get('failed_at')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'task_key': self.task_key,
            'runninghub_task_id': self.runninghub_task_id,
            'task_type': self.task_type,
            'user_id': self.user_id,
            'character_id': self.character_id,
            'character_name': self.character_name,
            'status': self.status,
            'try_count': self.try_count,
            'max_attempts': self.max_attempts,
            'error_message': self.error_message,
            'result_url': self.result_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
        }


class RunningHubAsyncTasksModel:
    """RunningHub 异步任务数据库操作"""

    @staticmethod
    def create(
        task_key: str,
        runninghub_task_id: str,
        task_type: str,
        user_id: int,
        character_id: Optional[int] = None,
        character_name: Optional[str] = None,
        style_prompt: Optional[str] = None,
        text: Optional[str] = None,
        max_attempts: int = 60
    ) -> int:
        """
        创建新的异步任务记录

        Args:
            task_key: 任务唯一键
            runninghub_task_id: RunningHub 返回的任务 ID
            task_type: 任务类型（如 "character_reference_audio"）
            user_id: 用户 ID
            character_id: 角色 ID（可选）
            character_name: 角色名称（可选）
            style_prompt: 音色风格提示词（可选）
            text: 朗读文本（可选）
            max_attempts: 最大轮询次数

        Returns:
            插入的记录 ID
        """
        sql = """
            INSERT INTO runninghub_async_tasks
            (task_key, runninghub_task_id, task_type, user_id, character_id,
             character_name, style_prompt, text, status, max_attempts)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            task_key, runninghub_task_id, task_type, user_id, character_id,
            character_name, style_prompt, text,
            RunningHubAsyncTaskStatus.QUEUED, max_attempts
        )

        try:
            record_id = execute_insert(sql, params)
            logger.info(f"Created RunningHub async task: {task_key}, record_id: {record_id}")
            return record_id
        except Exception as e:
            logger.error(f"Failed to create RunningHub async task {task_key}: {e}")
            raise

    @staticmethod
    def get_by_task_key(task_key: str) -> Optional[RunningHubAsyncTask]:
        """根据 task_key 获取任务"""
        sql = "SELECT * FROM runninghub_async_tasks WHERE task_key = %s"
        try:
            result = execute_query(sql, (task_key,), fetch_one=True)
            return RunningHubAsyncTask(**result) if result else None
        except Exception as e:
            logger.error(f"Failed to get RunningHub async task {task_key}: {e}")
            raise

    @staticmethod
    def get_pending_tasks(limit: int = 50) -> List[RunningHubAsyncTask]:
        """获取待处理的任务（状态为 QUEUED 或 PROCESSING）"""
        sql = """
            SELECT * FROM runninghub_async_tasks
            WHERE status IN (%s, %s)
            ORDER BY created_at ASC
            LIMIT %s
        """
        try:
            results = execute_query(
                sql,
                (RunningHubAsyncTaskStatus.QUEUED, RunningHubAsyncTaskStatus.PROCESSING, limit),
                fetch_all=True
            )
            return [RunningHubAsyncTask(**row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get pending RunningHub async tasks: {e}")
            raise

    @staticmethod
    def update_status(
        task_key: str,
        status: int,
        error_message: str = None,
        result_url: str = None
    ) -> int:
        """更新任务状态"""
        update_fields = ["status = %s"]
        params = [status]

        if error_message is not None:
            update_fields.append("error_message = %s")
            params.append(error_message)

        if result_url is not None:
            update_fields.append("result_url = %s")
            params.append(result_url)

        if status == RunningHubAsyncTaskStatus.COMPLETED:
            update_fields.append("completed_at = NOW()")
        elif status in (RunningHubAsyncTaskStatus.FAILED, RunningHubAsyncTaskStatus.TIMEOUT):
            update_fields.append("failed_at = NOW()")

        params.append(task_key)
        sql = f"UPDATE runninghub_async_tasks SET {', '.join(update_fields)} WHERE task_key = %s"

        try:
            affected = execute_update(sql, tuple(params))
            logger.info(f"Updated RunningHub async task {task_key} status to {status}")
            return affected
        except Exception as e:
            logger.error(f"Failed to update RunningHub async task {task_key}: {e}")
            raise

    @staticmethod
    def increment_try_count(task_key: str) -> int:
        """增加任务尝试次数"""
        sql = "UPDATE runninghub_async_tasks SET try_count = try_count + 1 WHERE task_key = %s"
        try:
            return execute_update(sql, (task_key,))
        except Exception as e:
            logger.error(f"Failed to increment try_count for {task_key}: {e}")
            raise

    @staticmethod
    def cleanup_old_tasks(days: int = 7) -> int:
        """清理旧任务"""
        sql = """
            DELETE FROM runninghub_async_tasks
            WHERE status IN (%s, %s, %s)
            AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        params = (
            RunningHubAsyncTaskStatus.COMPLETED,
            RunningHubAsyncTaskStatus.FAILED,
            RunningHubAsyncTaskStatus.TIMEOUT,
            days
        )
        try:
            affected = execute_update(sql, params)
            if affected > 0:
                logger.info(f"Cleaned up {affected} old RunningHub async tasks")
            return affected
        except Exception as e:
            logger.error(f"Failed to cleanup old RunningHub async tasks: {e}")
            raise


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `runninghub_async_tasks` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `task_key` varchar(255) NOT NULL COMMENT '任务唯一键',
  `runninghub_task_id` varchar(100) NOT NULL COMMENT 'RunningHub 任务 ID',
  `task_type` varchar(50) NOT NULL COMMENT '任务类型（如 character_reference_audio）',
  `user_id` int NOT NULL COMMENT '用户 ID',
  `character_id` int DEFAULT NULL COMMENT '角色 ID（用于更新 default_voice）',
  `character_name` varchar(255) DEFAULT NULL COMMENT '角色名称',
  `style_prompt` text COMMENT '音色风格提示词',
  `text` text COMMENT '朗读文本',
  `status` tinyint DEFAULT '0' COMMENT '状态（0-队列中, 1-处理中, 2-完成, -1-失败, -2-超时）',
  `try_count` int DEFAULT '0' COMMENT '轮询尝试次数',
  `max_attempts` int DEFAULT '60' COMMENT '最大尝试次数',
  `error_message` text COMMENT '错误信息',
  `result_url` varchar(1000) DEFAULT NULL COMMENT '结果音频 URL',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
  `failed_at` datetime DEFAULT NULL COMMENT '失败时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_key` (`task_key`),
  KEY `idx_status` (`status`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='RunningHub 异步任务表';
"""
