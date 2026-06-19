"""Add invite commission feature

新增邀请抽佣（商业版）数据结构：
- users 表新增 commission_rate（邀请人佣金比例，0~0.5；0=关闭抽佣）
- 新建 commission_log（邀请佣金明细/账本，单一数据源，纯账本式不维护聚合余额）
- 新建 commission_withdraw（佣金提现申请，不存金额，金额由 commission_log 聚合）

注意：新表/新列在社区版迁移也会建立，是否启用抽佣由代码层 IS_COMMUNITY_EDITION 守卫。

Revision ID: 20260613_invite_commission
Revises: 20260612_chat_messages
Create Date: 2026-06-13
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260613_invite_commission'
down_revision: Union[str, None] = '20260612_chat_messages'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _table_exists(conn, table: str) -> bool:
    """Check if a table exists"""
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
    ), {"table": table})
    return result.scalar() > 0


def _column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table"""
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column"
    ), {"table": table, "column": column})
    return result.scalar() > 0


def upgrade() -> None:
    conn = op.get_bind()

    # --- users 表新增 commission_rate ---
    if not _column_exists(conn, 'users', 'commission_rate'):
        conn.execute(text(
            "ALTER TABLE `users` "
            "ADD COLUMN `commission_rate` DECIMAL(5,4) NOT NULL DEFAULT 0.0000 "
            "COMMENT '邀请人佣金比例(0~0.5；0=关闭抽佣)' AFTER `inviter_id`"
        ))
        logger.info("Added column users.commission_rate")
    else:
        logger.info("Column users.commission_rate already exists, skipping")

    # --- commission_log ---
    if not _table_exists(conn, 'commission_log'):
        conn.execute(text("""
            CREATE TABLE `commission_log` (
              `id` int NOT NULL AUTO_INCREMENT,
              `inviter_id` int NOT NULL COMMENT '邀请人(佣金归属)ID',
              `invitee_id` int NOT NULL COMMENT '被邀请人(付款方)ID',
              `order_id` varchar(64) NOT NULL COMMENT '触发抽佣的订单号',
              `transaction_id` varchar(64) NOT NULL COMMENT '微信交易号(幂等键)',
              `package_id` int NOT NULL COMMENT '套餐ID',
              `order_amount` decimal(10,2) NOT NULL COMMENT '订单实付金额(元)',
              `commission_rate` decimal(5,4) NOT NULL COMMENT '本单抽佣比例快照',
              `commission_amount` decimal(10,2) NOT NULL COMMENT '本单佣金(元)',
              `granted_computing_power` int NOT NULL COMMENT '被邀请人到账算力(打折后)',
              `withdraw_no` varchar(64) DEFAULT NULL COMMENT '关联的提现单号；NULL=未提现',
              `status` tinyint NOT NULL DEFAULT 0 COMMENT '0-可用(未提现) 1-已提现 2-已冲正',
              `note` varchar(500) DEFAULT NULL,
              `create_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              UNIQUE KEY `uk_transaction_id` (`transaction_id`),
              KEY `idx_inviter_status` (`inviter_id`,`status`),
              KEY `idx_invitee` (`invitee_id`),
              KEY `idx_withdraw_no` (`withdraw_no`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邀请佣金明细表(用户佣金账本)'
        """))
        logger.info("Created table commission_log")
    else:
        logger.info("Table commission_log already exists, skipping")

    # --- commission_withdraw ---
    if not _table_exists(conn, 'commission_withdraw'):
        conn.execute(text("""
            CREATE TABLE `commission_withdraw` (
              `id` int NOT NULL AUTO_INCREMENT,
              `withdraw_no` varchar(64) NOT NULL COMMENT '提现单号',
              `inviter_id` int NOT NULL COMMENT '申请提现的邀请人ID',
              `status` tinyint NOT NULL DEFAULT 0 COMMENT '0-待审核 1-已打款 2-已驳回',
              `apply_note` varchar(500) DEFAULT NULL,
              `reject_reason` varchar(500) DEFAULT NULL,
              `reviewer_id` int DEFAULT NULL COMMENT '审核管理员ID',
              `reviewed_at` datetime DEFAULT NULL,
              `paid_at` datetime DEFAULT NULL,
              `create_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
              `update_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              UNIQUE KEY `uk_withdraw_no` (`withdraw_no`),
              KEY `idx_inviter_create` (`inviter_id`,`create_at`),
              KEY `idx_status_create` (`status`,`create_at`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='佣金提现申请表'
        """))
        logger.info("Created table commission_withdraw")
    else:
        logger.info("Table commission_withdraw already exists, skipping")


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, 'commission_withdraw'):
        conn.execute(text("DROP TABLE `commission_withdraw`"))
        logger.info("Dropped table commission_withdraw")

    if _table_exists(conn, 'commission_log'):
        conn.execute(text("DROP TABLE `commission_log`"))
        logger.info("Dropped table commission_log")

    if _column_exists(conn, 'users', 'commission_rate'):
        conn.execute(text("ALTER TABLE `users` DROP COLUMN `commission_rate`"))
        logger.info("Dropped column users.commission_rate")
