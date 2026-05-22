"""add label to media_file_mapping

Revision ID: 20260522_media_label
Revises: 20260522_add_sync_task
Create Date: 2026-05-22

为 media_file_mapping 表新增 label 字段（区分同一实体的不同媒体类型），
并将 UNIQUE KEY 从 (entity_type, source_id) 改为 (entity_type, source_id, label)。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260522_media_label'
down_revision: str = '20260522_add_sync_task'
branch_labels = None
depends_on = None

_BATCH_SIZE = 500


def upgrade() -> None:
    conn = op.get_bind()

    # 1. 检查 label 字段是否已存在
    check_column_sql = sa.text("""
        SELECT COUNT(*) as cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'media_file_mapping'
        AND COLUMN_NAME = 'label'
    """)
    column_exists = conn.execute(check_column_sql).scalar()

    if not column_exists:
        op.execute("""
            ALTER TABLE media_file_mapping
                ADD COLUMN `label` varchar(50) DEFAULT NULL
                    COMMENT '媒体标签，区分同一实体的不同媒体类型（image/voice）'
        """)

    # 2. 回填已有记录的 label 为 'image'
    updated = 0
    while True:
        rows = conn.execute(
            sa.text(
                "SELECT id FROM media_file_mapping "
                "WHERE label IS NULL "
                f"LIMIT {_BATCH_SIZE}"
            )
        ).fetchall()
        if not rows:
            break
        ids = [row[0] for row in rows]
        conn.execute(
            sa.text(
                "UPDATE media_file_mapping SET label = 'image' WHERE id IN :ids"
            ),
            {"ids": tuple(ids)}
        )
        updated += len(rows)
    if updated:
        print(f"[migration] 回填 label='image' 完成，共处理 {updated} 条记录")

    # 3. 删除旧 UNIQUE KEY，创建新的（包含 label）
    # 检查旧 UNIQUE KEY 是否存在
    check_old_key = sa.text("""
        SELECT COUNT(*) as cnt
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'media_file_mapping'
        AND INDEX_NAME = 'entity_type'
        AND NON_UNIQUE = 0
    """)
    old_key_exists = conn.execute(check_old_key).scalar()

    if old_key_exists:
        op.execute("ALTER TABLE media_file_mapping DROP INDEX `entity_type`")

    # 检查新 UNIQUE KEY 是否已存在
    check_new_key = sa.text("""
        SELECT COUNT(*) as cnt
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'media_file_mapping'
        AND INDEX_NAME = 'uk_entity_label'
        AND NON_UNIQUE = 0
    """)
    new_key_exists = conn.execute(check_new_key).scalar()

    if not new_key_exists:
        op.execute("""
            ALTER TABLE media_file_mapping
                ADD UNIQUE KEY `uk_entity_label` (`entity_type`, `source_id`, `label`)
        """)


def downgrade() -> None:
    conn = op.get_bind()

    # 删除新 UNIQUE KEY
    check_new_key = sa.text("""
        SELECT COUNT(*) as cnt
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'media_file_mapping'
        AND INDEX_NAME = 'uk_entity_label'
        AND NON_UNIQUE = 0
    """)
    new_key_exists = conn.execute(check_new_key).scalar()

    if new_key_exists:
        op.execute("ALTER TABLE media_file_mapping DROP INDEX `uk_entity_label`")

    # 恢复旧 UNIQUE KEY
    check_old_key = sa.text("""
        SELECT COUNT(*) as cnt
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'media_file_mapping'
        AND INDEX_NAME = 'entity_type'
        AND NON_UNIQUE = 0
    """)
    old_key_exists = conn.execute(check_old_key).scalar()

    if not old_key_exists:
        op.execute("""
            ALTER TABLE media_file_mapping
                ADD UNIQUE KEY `entity_type` (`entity_type`, `source_id`)
        """)

    # 删除 label 列
    check_column = sa.text("""
        SELECT COUNT(*) as cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'media_file_mapping'
        AND COLUMN_NAME = 'label'
    """)
    column_exists = conn.execute(check_column).scalar()

    if column_exists:
        op.execute("ALTER TABLE media_file_mapping DROP COLUMN `label`")
