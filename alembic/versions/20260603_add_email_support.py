"""Add email support to users and verify_codes tables

为用户表新增邮箱字段，支持邮箱注册和登录。
为验证码表新增邮箱和标识类型字段，支持邮箱验证码。

Revision ID: 20260603_email_support
Revises: 20260530_language
Create Date: 2026-06-03
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260603_email_support'
down_revision: Union[str, None] = '20260530_language'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table"""
    result = conn.execute(text(
        f"SELECT COUNT(*) FROM information_schema.COLUMNS "
        f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column"
    ), {"table": table, "column": column})
    return result.scalar() > 0


def _index_exists(conn, table: str, index: str) -> bool:
    """Check if an index exists in a table"""
    result = conn.execute(text(
        f"SELECT COUNT(*) FROM information_schema.STATISTICS "
        f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND INDEX_NAME = :index"
    ), {"table": table, "index": index})
    return result.scalar() > 0


def upgrade() -> None:
    """Add email support to users and verify_codes tables"""
    conn = op.get_bind()

    # ========== users 表 ==========

    # 1. 修改 phone 列为可空（允许纯邮箱用户）
    # 检查 phone 列当前是否为 NOT NULL
    col_info = conn.execute(text(
        "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'phone'"
    )).fetchone()

    if col_info and col_info[0] == 'NO':
        conn.execute(text("""
            ALTER TABLE `users`
            MODIFY COLUMN `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL
            COMMENT '手机号'
        """))
        logger.info("[Migration] Made users.phone nullable")
    else:
        logger.info("[Migration] users.phone already nullable, skipped")

    # 2. 新增 email 列
    if not _column_exists(conn, 'users', 'email'):
        conn.execute(text("""
            ALTER TABLE `users`
            ADD COLUMN `email` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL
            COMMENT '邮箱'
            AFTER `phone`
        """))
        logger.info("[Migration] Added email column to users table")
    else:
        logger.info("[Migration] Column email already exists in users, skipped")

    # 3. 新增 email 唯一索引
    if not _index_exists(conn, 'users', 'idx_email'):
        conn.execute(text("""
            ALTER TABLE `users`
            ADD UNIQUE KEY `idx_email` (`email`)
        """))
        logger.info("[Migration] Added idx_email unique index to users table")
    else:
        logger.info("[Migration] Index idx_email already exists, skipped")

    # ========== verify_codes 表 ==========

    # 4. 修改 phone 列为可空
    col_info_vc = conn.execute(text(
        "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'verify_codes' AND COLUMN_NAME = 'phone'"
    )).fetchone()

    if col_info_vc and col_info_vc[0] == 'NO':
        conn.execute(text("""
            ALTER TABLE `verify_codes`
            MODIFY COLUMN `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL
            COMMENT '手机号'
        """))
        logger.info("[Migration] Made verify_codes.phone nullable")
    else:
        logger.info("[Migration] verify_codes.phone already nullable, skipped")

    # 5. 新增 email 列
    if not _column_exists(conn, 'verify_codes', 'email'):
        conn.execute(text("""
            ALTER TABLE `verify_codes`
            ADD COLUMN `email` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL
            COMMENT '邮箱'
            AFTER `phone`
        """))
        logger.info("[Migration] Added email column to verify_codes table")
    else:
        logger.info("[Migration] Column email already exists in verify_codes, skipped")

    # 6. 新增 identifier_type 列
    if not _column_exists(conn, 'verify_codes', 'identifier_type'):
        conn.execute(text("""
            ALTER TABLE `verify_codes`
            ADD COLUMN `identifier_type` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'phone'
            COMMENT '标识类型：phone或email'
            AFTER `email`
        """))
        logger.info("[Migration] Added identifier_type column to verify_codes table")
    else:
        logger.info("[Migration] Column identifier_type already exists in verify_codes, skipped")

    # 7. 新增 email+type 索引
    if not _index_exists(conn, 'verify_codes', 'idx_email_type'):
        conn.execute(text("""
            ALTER TABLE `verify_codes`
            ADD KEY `idx_email_type` (`email`, `type`)
        """))
        logger.info("[Migration] Added idx_email_type index to verify_codes table")
    else:
        logger.info("[Migration] Index idx_email_type already exists, skipped")


def downgrade() -> None:
    """Remove email support from users and verify_codes tables"""
    conn = op.get_bind()

    # ========== verify_codes 表 ==========
    if _index_exists(conn, 'verify_codes', 'idx_email_type'):
        conn.execute(text("ALTER TABLE `verify_codes` DROP INDEX `idx_email_type`"))
        logger.info("[Migration] Removed idx_email_type index from verify_codes")

    if _column_exists(conn, 'verify_codes', 'identifier_type'):
        conn.execute(text("ALTER TABLE `verify_codes` DROP COLUMN `identifier_type`"))
        logger.info("[Migration] Removed identifier_type column from verify_codes")

    if _column_exists(conn, 'verify_codes', 'email'):
        conn.execute(text("ALTER TABLE `verify_codes` DROP COLUMN `email`"))
        logger.info("[Migration] Removed email column from verify_codes")

    conn.execute(text("""
        ALTER TABLE `verify_codes`
        MODIFY COLUMN `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL
        COMMENT '手机号'
    """))
    logger.info("[Migration] Made verify_codes.phone NOT NULL again")

    # ========== users 表 ==========
    if _index_exists(conn, 'users', 'idx_email'):
        conn.execute(text("ALTER TABLE `users` DROP INDEX `idx_email`"))
        logger.info("[Migration] Removed idx_email index from users")

    if _column_exists(conn, 'users', 'email'):
        conn.execute(text("ALTER TABLE `users` DROP COLUMN `email`"))
        logger.info("[Migration] Removed email column from users")

    conn.execute(text("""
        ALTER TABLE `users`
        MODIFY COLUMN `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL
        COMMENT '手机号'
    """))
    logger.info("[Migration] Made users.phone NOT NULL again")
