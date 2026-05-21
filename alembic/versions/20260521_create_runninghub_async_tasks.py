"""create runninghub_async_tasks table

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
    """创建 runninghub_async_tasks 表"""
    op.execute("""
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
    """)


def downgrade():
    """删除 runninghub_async_tasks 表"""
    op.execute("DROP TABLE IF EXISTS `runninghub_async_tasks`")
