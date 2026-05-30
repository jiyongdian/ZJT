"""20260527 批量迁移：pipeline_steps + async_tasks 重试支持

Revision ID: 202605270001_merge
Revises: 20260526_async_slot_support
Create Date: 2026-05-27

合并以下迁移：
- 创建 ai_tool_pipeline_steps 表（含重试、result_url、target 字段）
- 添加 async_tasks 重试字段
- 修复 runninghub_slots 唯一键为 (task_id, source)
"""
from alembic import op
import sqlalchemy as sa

revision = '202605270001_merge'
down_revision = '20260526_async_slot_support'
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    """检查列是否存在"""
    return conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND COLUMN_NAME=:col"
    ), {'table': table, 'col': column}).scalar() > 0


def _index_exists(conn, table: str, index_name: str) -> bool:
    """检查索引是否存在"""
    return conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND INDEX_NAME=:idx"
    ), {'table': table, 'idx': index_name}).scalar() > 0


def _table_exists(conn, table: str) -> bool:
    """检查表是否存在"""
    return conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table"
    ), {'table': table}).scalar() > 0


def upgrade() -> None:
    conn = op.get_bind()

    # ========== 1. ai_tool_pipeline_steps 表 ==========
    if not _table_exists(conn, 'ai_tool_pipeline_steps'):
        op.execute("""
            CREATE TABLE `ai_tool_pipeline_steps` (
              `id` int NOT NULL AUTO_INCREMENT,
              `ai_tool_id` int NOT NULL COMMENT '关联 ai_tools.id',
              `stage` varchar(32) NOT NULL COMMENT '阶段: param_prepare | before_finish',
              `step_type` varchar(64) NOT NULL COMMENT '步骤类型: face_mask | implementation_retry',
              `target` text DEFAULT NULL COMMENT '步骤目标（如对应的 video_path）',
              `step_order` int NOT NULL DEFAULT 0 COMMENT '同阶段内执行顺序（0 起始）',
              `status` tinyint NOT NULL DEFAULT 0 COMMENT '0=pending, 1=processing, 2=completed, -1=failed, -2=timeout',
              `params` json DEFAULT NULL COMMENT '步骤参数（JSON 格式）',
              `result_data` json DEFAULT NULL COMMENT '步骤结果数据（JSON 格式）',
              `result_url` text DEFAULT NULL COMMENT '结果文件路径（本地路径或远程 URL）',
              `error_message` text COMMENT '错误信息',
              `async_task_id` int DEFAULT NULL COMMENT '关联 async_tasks.id',
              `retry_count` int NOT NULL DEFAULT 0 COMMENT '重试次数',
              `next_retry_at` datetime DEFAULT NULL COMMENT '下次重试时间',
              `max_retries` int NOT NULL DEFAULT 5 COMMENT '最大重试次数',
              `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
              `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              `completed_at` datetime DEFAULT NULL,
              PRIMARY KEY (`id`),
              KEY `idx_ai_tool_stage_status` (`ai_tool_id`, `stage`, `status`),
              KEY `idx_status_updated` (`status`, `updated_at`),
              KEY `idx_async_task_id` (`async_task_id`),
              KEY `idx_retry_ready` (`status`, `next_retry_at`, `retry_count`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            COMMENT='AI工具流水线步骤表'
        """)
    else:
        # 表已存在，补充缺失的列
        for col_name, col_type, after_col in [
            ('target', 'text DEFAULT NULL COMMENT \'步骤目标\'', 'step_type'),
            ('result_url', 'text DEFAULT NULL COMMENT \'结果文件路径\'', 'result_data'),
            ('retry_count', 'int NOT NULL DEFAULT 0 COMMENT \'重试次数\'', 'async_task_id'),
            ('next_retry_at', 'datetime DEFAULT NULL COMMENT \'下次重试时间\'', 'retry_count'),
            ('max_retries', 'int NOT NULL DEFAULT 5 COMMENT \'最大重试次数\'', 'next_retry_at'),
        ]:
            if not _column_exists(conn, 'ai_tool_pipeline_steps', col_name):
                op.execute(
                    f"ALTER TABLE `ai_tool_pipeline_steps` ADD COLUMN `{col_name}` {col_type} AFTER `{after_col}`"
                )

        # 补充缺失的索引
        if not _index_exists(conn, 'ai_tool_pipeline_steps', 'idx_retry_ready'):
            op.execute(
                "ALTER TABLE `ai_tool_pipeline_steps` ADD KEY `idx_retry_ready` (`status`, `next_retry_at`, `retry_count`)"
            )

    # ========== 2. async_tasks 重试字段 ==========
    for col_name, col_def in [
        ('retry_count', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0', comment='重试次数')),
        ('next_retry_at', sa.Column('next_retry_at', sa.DateTime(), nullable=True, comment='下次重试时间')),
        ('max_retries', sa.Column('max_retries', sa.Integer(), nullable=False, server_default='5', comment='最大重试次数')),
    ]:
        if not _column_exists(conn, 'async_tasks', col_name):
            op.add_column('async_tasks', col_def)

    if not _index_exists(conn, 'async_tasks', 'idx_async_task_retry_ready'):
        op.create_index('idx_async_task_retry_ready', 'async_tasks',
            ['status', 'next_retry_at', 'retry_count'], unique=False)

    # ========== 3. 修复 runninghub_slots 唯一键 ==========
    if _index_exists(conn, 'runninghub_slots', 'uk_task_table_id_source'):
        op.execute("ALTER TABLE `runninghub_slots` DROP INDEX `uk_task_table_id_source`")

    if not _index_exists(conn, 'runninghub_slots', 'uk_task_id_source'):
        op.execute("ALTER TABLE `runninghub_slots` ADD UNIQUE KEY `uk_task_id_source` (`task_id`, `source`)")

    # 清理旧数据（task_id=0 且 source='async' 的脏数据）
    result = conn.execute(sa.text("SELECT COUNT(*) as cnt FROM runninghub_slots WHERE task_id = 0 AND source = 'async'"))
    count = result.fetchone()[0] if result else 0
    if count > 0:
        conn.execute(sa.text("DELETE FROM runninghub_slots WHERE task_id = 0 AND source = 'async'"))
        print(f"[Migration] Deleted {count} stale async slots with task_id=0")


def downgrade() -> None:
    conn = op.get_bind()

    # ========== 1. 回滚 runninghub_slots ==========
    if _index_exists(conn, 'runninghub_slots', 'uk_task_id_source'):
        op.execute("ALTER TABLE `runninghub_slots` DROP INDEX `uk_task_id_source`")
    if not _index_exists(conn, 'runninghub_slots', 'uk_task_table_id_source'):
        op.execute("ALTER TABLE `runninghub_slots` ADD UNIQUE KEY `uk_task_table_id_source` (`task_table_id`, `source`)")

    # ========== 2. 回滚 async_tasks ==========
    if _index_exists(conn, 'async_tasks', 'idx_async_task_retry_ready'):
        op.drop_index('idx_async_task_retry_ready', table_name='async_tasks')
    for col in ['max_retries', 'next_retry_at', 'retry_count']:
        if _column_exists(conn, 'async_tasks', col):
            op.drop_column('async_tasks', col)

    # ========== 3. 删除 ai_tool_pipeline_steps 表 ==========
    op.execute("DROP TABLE IF EXISTS `ai_tool_pipeline_steps`")
