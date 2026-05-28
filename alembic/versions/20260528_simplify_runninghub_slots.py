"""20260528 简化 runninghub_slots 表：删除 task_table_id 和 async_task_id

Revision ID: 20260528_simplify_slots
Revises: 202605270001_merge
Create Date: 2026-05-28

重构 runninghub_slots 表：
- 删除 task_table_id 列（原存储 ai_tools.id，release 函数因参数映射 BUG 从未正确匹配）
- 删除 async_task_id 列（与 task_id 在 source='async' 时完全冗余）
- 保留 task_id + source 唯一键（task_id 存储源表主键：tasks.id 或 async_tasks.id）
- 清理泄漏的活跃槽位
"""
from alembic import op
import sqlalchemy as sa

revision = '20260528_simplify_slots'
down_revision = '202605270001_merge'
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    return conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND COLUMN_NAME=:col"
    ), {'table': table, 'col': column}).scalar() > 0


def _index_exists(conn, table: str, index_name: str) -> bool:
    return conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND INDEX_NAME=:idx"
    ), {'table': table, 'idx': index_name}).scalar() > 0


def upgrade() -> None:
    conn = op.get_bind()

    # 1. 清理泄漏的活跃槽位（超过 10 分钟未释放的视为泄漏）
    conn.execute(sa.text(
        "UPDATE runninghub_slots SET status = 2, released_at = NOW() "
        "WHERE status = 1 AND acquired_at < DATE_SUB(NOW(), INTERVAL 10 MINUTE)"
    ))

    # 2. 删除 async_task_id 索引和列
    if _index_exists(conn, 'runninghub_slots', 'idx_async_task_id'):
        op.execute("ALTER TABLE `runninghub_slots` DROP INDEX `idx_async_task_id`")

    if _column_exists(conn, 'runninghub_slots', 'async_task_id'):
        op.execute("ALTER TABLE `runninghub_slots` DROP COLUMN `async_task_id`")

    # 3. 删除 task_table_id 列
    if _column_exists(conn, 'runninghub_slots', 'task_table_id'):
        op.execute("ALTER TABLE `runninghub_slots` DROP COLUMN `task_table_id`")

    # 4. 更新 task_id 列注释
    op.execute(
        "ALTER TABLE `runninghub_slots` "
        "MODIFY COLUMN `task_id` int unsigned NOT NULL DEFAULT '0' "
        "COMMENT 'source=task 时存 tasks.id，source=async 时存 async_tasks.id'"
    )


def downgrade() -> None:
    conn = op.get_bind()

    # 恢复 task_table_id 列
    if not _column_exists(conn, 'runninghub_slots', 'task_table_id'):
        op.execute(
            "ALTER TABLE `runninghub_slots` "
            "ADD COLUMN `task_table_id` int unsigned NOT NULL DEFAULT '0' "
            "COMMENT 'tasks表主键id' AFTER `task_id`"
        )

    # 恢复 async_task_id 列
    if not _column_exists(conn, 'runninghub_slots', 'async_task_id'):
        op.execute(
            "ALTER TABLE `runninghub_slots` "
            "ADD COLUMN `async_task_id` int DEFAULT NULL "
            "COMMENT 'async_tasks表主键id' AFTER `source`"
        )

    # 恢复 async_task_id 索引
    if not _index_exists(conn, 'runninghub_slots', 'idx_async_task_id'):
        op.execute(
            "ALTER TABLE `runninghub_slots` ADD KEY `idx_async_task_id` (`async_task_id`)"
        )

    # 恢复 task_id 列注释
    op.execute(
        "ALTER TABLE `runninghub_slots` "
        "MODIFY COLUMN `task_id` int unsigned NOT NULL DEFAULT '0' "
        "COMMENT 'tasks表主键id（SOURCE_TASK）或async_tasks表主键id（SOURCE_ASYNC）'"
    )
