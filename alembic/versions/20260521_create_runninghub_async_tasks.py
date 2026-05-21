"""create async_tasks table

Revision ID: 20260521_001
Revises: 20260520_zjt_api_doubao
Create Date: 2026-05-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260521_001'
down_revision = '20260520_zjt_api_doubao'
branch_labels = None
depends_on = None


def upgrade():
    """创建 async_tasks 表（通用异步任务表）"""
    op.execute("""
        CREATE TABLE IF NOT EXISTS `async_tasks` (
          `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
          `implementation` int unsigned NOT NULL DEFAULT '0' COMMENT '实现 ID（参考 AsyncTaskImplementationId）',
          `external_task_id` varchar(100) DEFAULT NULL COMMENT '外部任务 ID（如 RunningHub taskId）',
          `user_id` int NOT NULL COMMENT '用户 ID',
          `params` json DEFAULT NULL COMMENT '任务参数（JSON 格式，implementation 特定）',
          `status` tinyint DEFAULT '0' COMMENT '状态（0-队列中, 1-处理中, 2-完成, -1-失败, -2-超时）',
          `try_count` int DEFAULT '0' COMMENT '轮询尝试次数',
          `max_attempts` int DEFAULT '25' COMMENT '最大尝试次数',
          `error_message` text COMMENT '错误信息',
          `result_url` varchar(1000) DEFAULT NULL COMMENT '结果 URL',
          `result_data` json DEFAULT NULL COMMENT '额外结果数据（JSON 格式）',
          `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
          `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
          `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
          `failed_at` datetime DEFAULT NULL COMMENT '失败时间',
          PRIMARY KEY (`id`),
          KEY `idx_user_id` (`user_id`),
          KEY `idx_impl_status` (`implementation`, `status`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='通用异步任务表';
    """)


def downgrade():
    """删除 async_tasks 表"""
    op.execute("DROP TABLE IF EXISTS `async_tasks`")
