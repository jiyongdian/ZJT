"""
Async Tasks Model - Database operations for async_tasks table
通用异步任务模型 - 支持多进程环境下的异步任务状态共享

参考 ai_tools 的 implementation 模式，通过 implementation (数字 ID) 区分不同的异步驱动，
每个驱动负责自己的 params 序列化/反序列化和业务逻辑。

使用方式：
1. API 提交任务时，指定 implementation (数字 ID) 和 params（JSON 格式）
2. Driver 负责将 params 提交到外部服务
3. Scheduler 后台轮询，调用 Driver 的 check_status() 方法
4. Driver 根据结果更新数据库
"""
from typing import List, Optional, Dict, Any
from .database import execute_query, execute_update, execute_insert
import logging
import json

logger = logging.getLogger(__name__)


class AsyncTaskStatus:
    """异步任务状态常量"""
    QUEUED = 0          # 队列中（已提交到外部服务）
    PROCESSING = 1      # 处理中（正在轮询）
    COMPLETED = 2       # 完成
    FAILED = -1         # 失败
    TIMEOUT = -2        # 超时


class AsyncTask:
    """异步任务模型"""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.task_key = kwargs.get('task_key')
        self.implementation = kwargs.get('implementation')  # 改为 implementation (int)
        self.external_task_id = kwargs.get('external_task_id')
        self.user_id = kwargs.get('user_id')
        self.params = kwargs.get('params')  # JSON 字符串或已解析的 dict
        self.status = kwargs.get('status', AsyncTaskStatus.QUEUED)
        self.try_count = kwargs.get('try_count', 0)
        self.max_attempts = kwargs.get('max_attempts', 60)
        self.error_message = kwargs.get('error_message')
        self.result_url = kwargs.get('result_url')
        self.result_data = kwargs.get('result_data')  # JSON 字符串或已解析的 dict
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        self.completed_at = kwargs.get('completed_at')
        self.failed_at = kwargs.get('failed_at')

    def get_params_dict(self) -> Dict[str, Any]:
        """获取解析后的 params 字典"""
        if isinstance(self.params, dict):
            return self.params
        if isinstance(self.params, str):
            try:
                return json.loads(self.params)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse params as JSON: {self.params}")
                return {}
        return {}

    def get_result_data_dict(self) -> Dict[str, Any]:
        """获取解析后的 result_data 字典"""
        if isinstance(self.result_data, dict):
            return self.result_data
        if isinstance(self.result_data, str):
            try:
                return json.loads(self.result_data)
            except json.JSONDecodeError:
                return {}
        return {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'task_key': self.task_key,
            'implementation': self.implementation,
            'external_task_id': self.external_task_id,
            'user_id': self.user_id,
            'params': self.get_params_dict(),
            'status': self.status,
            'try_count': self.try_count,
            'max_attempts': self.max_attempts,
            'error_message': self.error_message,
            'result_url': self.result_url,
            'result_data': self.get_result_data_dict(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
        }


class AsyncTasksModel:
    """异步任务数据库操作"""

    @staticmethod
    def create(
        task_key: str,
        implementation: int,
        user_id: int,
        external_task_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        max_attempts: int = 60
    ) -> int:
        """
        创建新的异步任务记录

        Args:
            task_key: 任务唯一键
            implementation: 实现 ID（参考 AsyncTaskImplementationId 常量）
            user_id: 用户 ID
            external_task_id: 外部任务 ID（可选，如 RunningHub taskId）
            params: 任务参数（JSON 可序列化对象）
            max_attempts: 最大轮询次数

        Returns:
            插入的记录 ID
        """
        params_json = json.dumps(params) if params else None

        sql = """
            INSERT INTO async_tasks
            (task_key, implementation, user_id, external_task_id, params, status, max_attempts)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        db_params = (
            task_key, implementation, user_id, external_task_id,
            params_json, AsyncTaskStatus.QUEUED, max_attempts
        )

        try:
            record_id = execute_insert(sql, db_params)
            logger.info(f"Created async task: {task_key}, implementation: {implementation}, record_id: {record_id}")
            return record_id
        except Exception as e:
            logger.error(f"Failed to create async task {task_key}: {e}")
            raise

    @staticmethod
    def get_by_task_key(task_key: str) -> Optional[AsyncTask]:
        """根据 task_key 获取任务"""
        sql = "SELECT * FROM async_tasks WHERE task_key = %s"
        try:
            result = execute_query(sql, (task_key,), fetch_one=True)
            return AsyncTask(**result) if result else None
        except Exception as e:
            logger.error(f"Failed to get async task {task_key}: {e}")
            raise

    @staticmethod
    def get_by_implementation(
        implementation: int,
        status: Optional[int] = None,
        limit: int = 50
    ) -> List[AsyncTask]:
        """
        根据实现 ID 获取任务列表

        Args:
            implementation: 实现 ID
            status: 状态筛选（可选）
            limit: 最大返回数量

        Returns:
            AsyncTask 对象列表
        """
        if status is not None:
            sql = """
                SELECT * FROM async_tasks
                WHERE implementation = %s AND status = %s
                ORDER BY created_at ASC
                LIMIT %s
            """
            params = (implementation, status, limit)
        else:
            sql = """
                SELECT * FROM async_tasks
                WHERE implementation = %s
                ORDER BY created_at ASC
                LIMIT %s
            """
            params = (implementation, limit)

        try:
            results = execute_query(sql, params, fetch_all=True)
            return [AsyncTask(**row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get async tasks by implementation {implementation}: {e}")
            raise

    @staticmethod
    def get_pending_tasks(implementation: Optional[int] = None, limit: int = 50) -> List[AsyncTask]:
        """
        获取待处理的任务（状态为 QUEUED 或 PROCESSING）

        Args:
            implementation: 实现 ID 筛选（可选，不传则获取所有实现的任务）
            limit: 最大返回数量

        Returns:
            AsyncTask 对象列表
        """
        if implementation:
            sql = """
                SELECT * FROM async_tasks
                WHERE implementation = %s AND status IN (%s, %s)
                ORDER BY created_at ASC
                LIMIT %s
            """
            params = (implementation, AsyncTaskStatus.QUEUED, AsyncTaskStatus.PROCESSING, limit)
        else:
            sql = """
                SELECT * FROM async_tasks
                WHERE status IN (%s, %s)
                ORDER BY created_at ASC
                LIMIT %s
            """
            params = (AsyncTaskStatus.QUEUED, AsyncTaskStatus.PROCESSING, limit)

        try:
            results = execute_query(sql, params, fetch_all=True)
            return [AsyncTask(**row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get pending async tasks: {e}")
            raise

    @staticmethod
    def get_user_tasks(user_id: int, implementation: Optional[int] = None, limit: int = 50) -> List[AsyncTask]:
        """
        获取用户的任务列表

        Args:
            user_id: 用户 ID
            implementation: 实现 ID 筛选（可选）
            limit: 最大返回数量

        Returns:
            AsyncTask 对象列表
        """
        if implementation:
            sql = """
                SELECT * FROM async_tasks
                WHERE user_id = %s AND implementation = %s
                ORDER BY created_at DESC
                LIMIT %s
            """
            params = (user_id, implementation, limit)
        else:
            sql = """
                SELECT * FROM async_tasks
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """
            params = (user_id, limit)

        try:
            results = execute_query(sql, params, fetch_all=True)
            return [AsyncTask(**row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get user async tasks: {e}")
            raise

    @staticmethod
    def update_status(
        task_key: str,
        status: int,
        error_message: str = None,
        result_url: str = None,
        result_data: Dict[str, Any] = None
    ) -> int:
        """
        更新任务状态

        Args:
            task_key: 任务唯一键
            status: 新状态
            error_message: 错误信息（可选）
            result_url: 结果 URL（可选）
            result_data: 额外结果数据（可选，JSON 可序列化对象）

        Returns:
            影响的行数
        """
        update_fields = ["status = %s"]
        params = [status]

        if error_message is not None:
            update_fields.append("error_message = %s")
            params.append(error_message)

        if result_url is not None:
            update_fields.append("result_url = %s")
            params.append(result_url)

        if result_data is not None:
            update_fields.append("result_data = %s")
            params.append(json.dumps(result_data))

        # 根据状态设置完成/失败时间
        if status == AsyncTaskStatus.COMPLETED:
            update_fields.append("completed_at = NOW()")
        elif status in (AsyncTaskStatus.FAILED, AsyncTaskStatus.TIMEOUT):
            update_fields.append("failed_at = NOW()")

        params.append(task_key)
        sql = f"UPDATE async_tasks SET {', '.join(update_fields)} WHERE task_key = %s"

        try:
            affected = execute_update(sql, tuple(params))
            logger.info(f"Updated async task {task_key} status to {status}")
            return affected
        except Exception as e:
            logger.error(f"Failed to update async task {task_key}: {e}")
            raise

    @staticmethod
    def update_external_task_id(task_key: str, external_task_id: str) -> int:
        """更新外部任务 ID（用于任务提交后回填）"""
        sql = "UPDATE async_tasks SET external_task_id = %s WHERE task_key = %s"
        try:
            affected = execute_update(sql, (external_task_id, task_key))
            logger.info(f"Updated external_task_id for {task_key}: {external_task_id}")
            return affected
        except Exception as e:
            logger.error(f"Failed to update external_task_id for {task_key}: {e}")
            raise

    @staticmethod
    def increment_try_count(task_key: str) -> int:
        """增加任务尝试次数"""
        sql = "UPDATE async_tasks SET try_count = try_count + 1 WHERE task_key = %s"
        try:
            return execute_update(sql, (task_key,))
        except Exception as e:
            logger.error(f"Failed to increment try_count for {task_key}: {e}")
            raise

    @staticmethod
    def cleanup_old_tasks(days: int = 7, implementation: Optional[int] = None) -> int:
        """
        清理旧任务

        Args:
            days: 保留天数
            implementation: 实现 ID 筛选（可选）

        Returns:
            删除的行数
        """
        if implementation:
            sql = """
                DELETE FROM async_tasks
                WHERE implementation = %s
                  AND status IN (%s, %s, %s)
                  AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            params = (
                implementation,
                AsyncTaskStatus.COMPLETED,
                AsyncTaskStatus.FAILED,
                AsyncTaskStatus.TIMEOUT,
                days
            )
        else:
            sql = """
                DELETE FROM async_tasks
                WHERE status IN (%s, %s, %s)
                AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            params = (
                AsyncTaskStatus.COMPLETED,
                AsyncTaskStatus.FAILED,
                AsyncTaskStatus.TIMEOUT,
                days
            )

        try:
            affected = execute_update(sql, params)
            if affected > 0:
                logger.info(f"Cleaned up {affected} old async tasks (older than {days} days)")
            return affected
        except Exception as e:
            logger.error(f"Failed to cleanup old async tasks: {e}")
            raise


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `async_tasks` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `task_key` varchar(255) NOT NULL COMMENT '任务唯一键',
  `implementation` int unsigned NOT NULL DEFAULT '0' COMMENT '实现 ID（参考 AsyncTaskImplementationId）',
  `external_task_id` varchar(100) DEFAULT NULL COMMENT '外部任务 ID（如 RunningHub taskId）',
  `user_id` int NOT NULL COMMENT '用户 ID',
  `params` json DEFAULT NULL COMMENT '任务参数（JSON 格式，implementation 特定）',
  `status` tinyint DEFAULT '0' COMMENT '状态（0-队列中, 1-处理中, 2-完成, -1-失败, -2-超时）',
  `try_count` int DEFAULT '0' COMMENT '轮询尝试次数',
  `max_attempts` int DEFAULT '60' COMMENT '最大尝试次数',
  `error_message` text COMMENT '错误信息',
  `result_url` varchar(1000) DEFAULT NULL COMMENT '结果 URL',
  `result_data` json DEFAULT NULL COMMENT '额外结果数据（JSON 格式）',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
  `failed_at` datetime DEFAULT NULL COMMENT '失败时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_key` (`task_key`),
  KEY `idx_implementation` (`implementation`),
  KEY `idx_status` (`status`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_impl_status` (`implementation`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='通用异步任务表';
"""
