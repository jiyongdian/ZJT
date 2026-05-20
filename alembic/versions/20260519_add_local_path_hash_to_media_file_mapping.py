"""add_local_path_hash_to_media_file_mapping

Revision ID: 20260519_local_path_hash
Revises: 20260515_mkt_world
Create Date: 2026-05-19

为 media_file_mapping 表新增 local_path_hash 字段（SHA256）及索引，
用于 CDN 重定向时快速查找记录。
"""
import hashlib

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260519_local_path_hash'
down_revision: str = '20260515_mkt_world'
branch_labels = None
depends_on = None

# 每批次处理的记录数，避免一次性加载过多数据
_BATCH_SIZE = 500


def _compute_hash(local_path: str) -> str:
    """统一使用正斜杠计算 hash，与 model 层逻辑一致"""
    normalized = local_path.replace('\\', '/')
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()

    # 检查 local_path_hash 字段是否已存在
    check_column_sql = sa.text("""
        SELECT COUNT(*) as cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'media_file_mapping'
        AND COLUMN_NAME = 'local_path_hash'
    """)
    column_exists = conn.execute(check_column_sql).scalar()

    if not column_exists:
        # 字段不存在，添加字段和索引
        op.execute("""
            ALTER TABLE media_file_mapping
                ADD COLUMN `local_path_hash` varchar(64) DEFAULT NULL
                    COMMENT 'local_path 的 SHA256 哈希，用于快速 CDN 重定向查找',
                ADD KEY `idx_local_path_hash` (`local_path_hash`)
        """)

    # 回填已有记录的 local_path_hash（即使字段已存在，也可能有 NULL 值需要回填）
    updated = 0
    while True:
        rows = conn.execute(
            sa.text(
                "SELECT id, local_path FROM media_file_mapping "
                "WHERE local_path_hash IS NULL AND local_path IS NOT NULL "
                f"LIMIT {_BATCH_SIZE}"
            )
        ).fetchall()
        if not rows:
            break
        for row in rows:
            record_id, local_path = row[0], row[1]
            url_hash = _compute_hash(local_path)
            conn.execute(
                sa.text(
                    "UPDATE media_file_mapping SET local_path_hash = :hash WHERE id = :id"
                ),
                {"hash": url_hash, "id": record_id}
            )
        updated += len(rows)
    if updated:
        print(f"[migration] 回填 local_path_hash 完成，共处理 {updated} 条记录")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE media_file_mapping
            DROP KEY `idx_local_path_hash`,
            DROP COLUMN `local_path_hash`
    """)
