"""add async slot support to runninghub_slots

Revision ID: 20260526_async_slot_support
Revises: 20260526_upload_max_video_size
Create Date: 2026-05-26

为 runninghub_slots 表添加异步任务支持：
- 新增 source 字段区分旧任务系统和异步任务系统
- 新增 async_task_id 字段关联 async_tasks 表
- 修改唯一键包含 source 字段
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260526_async_slot_support'
down_revision = '20260526_upload_max_video_size'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 添加 source 字段（默认 'task' 兼容旧数据）
    op.execute("""
        ALTER TABLE `runninghub_slots`
        ADD COLUMN `source` varchar(10) NOT NULL DEFAULT 'task'
        COMMENT '来源: task-旧任务系统, async-异步任务系统'
        AFTER `task_type`
    """)

    # 2. 添加 async_task_id 字段
    op.execute("""
        ALTER TABLE `runninghub_slots`
        ADD COLUMN `async_task_id` int DEFAULT NULL
        COMMENT 'async_tasks表的主键id（仅source=async时有值）'
        AFTER `source`
    """)

    # 3. 删除旧的唯一键，添加新的唯一键（包含 source）
    op.execute("""
        ALTER TABLE `runninghub_slots`
        DROP INDEX `uk_task_table_id`,
        ADD UNIQUE KEY `uk_task_table_id_source` (`task_table_id`, `source`)
    """)

    # 4. 添加 async_task_id 索引
    op.execute("""
        ALTER TABLE `runninghub_slots`
        ADD KEY `idx_async_task_id` (`async_task_id`)
    """)

    # 5. 修改 task_id 和 task_table_id 允许默认值 0（异步任务不需要这两个字段）
    op.execute("""
        ALTER TABLE `runninghub_slots`
        MODIFY COLUMN `task_id` int unsigned NOT NULL DEFAULT '0'
        COMMENT 'tasks表的task_id (ai_tools.id)，异步任务为0',
        MODIFY COLUMN `task_table_id` int unsigned NOT NULL DEFAULT '0'
        COMMENT 'tasks表的主键id，异步任务为0'
    """)


def downgrade() -> None:
    # 1. 恢复 task_id 和 task_table_id 的原始定义
    op.execute("""
        ALTER TABLE `runninghub_slots`
        MODIFY COLUMN `task_id` int unsigned NOT NULL
        COMMENT 'tasks表的task_id (ai_tools.id)',
        MODIFY COLUMN `task_table_id` int unsigned NOT NULL
        COMMENT 'tasks表的主键id'
    """)

    # 2. 删除 async_task_id 索引
    op.execute("ALTER TABLE `runninghub_slots` DROP INDEX `idx_async_task_id`")

    # 3. 恢复旧的唯一键
    op.execute("""
        ALTER TABLE `runninghub_slots`
        DROP INDEX `uk_task_table_id_source`,
        ADD UNIQUE KEY `uk_task_table_id` (`task_table_id`)
    """)

    # 4. 删除 async_task_id 和 source 字段
    op.execute("""
        ALTER TABLE `runninghub_slots`
        DROP COLUMN `async_task_id`,
        DROP COLUMN `source`
    """)
