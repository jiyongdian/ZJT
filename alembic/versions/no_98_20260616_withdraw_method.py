"""Add withdraw method fields to commission_withdraw

佣金提现申请增加提现方式信息，供管理员查看并打款：
- method: 提现方式 (alipay-支付宝 / bank-银行卡)
- alipay_account: 支付宝账号
- bank_card_no / bank_account_name / bank_name: 银行卡号 / 开户姓名 / 开户银行

Revision ID: 20260616_withdraw_method
Revises: 20260613_invite_commission
Create Date: 2026-06-16
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260616_withdraw_method'
down_revision: Union[str, None] = '20260613_invite_commission'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table"""
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column"
    ), {"table": table, "column": column})
    return result.scalar() > 0


def upgrade() -> None:
    conn = op.get_bind()

    additions = [
        ("method", "ADD COLUMN `method` varchar(16) NOT NULL DEFAULT 'alipay' COMMENT '提现方式: alipay-支付宝 bank-银行卡' AFTER `status`"),
        ("alipay_account", "ADD COLUMN `alipay_account` varchar(128) DEFAULT NULL COMMENT '支付宝账号' AFTER `method`"),
        ("bank_card_no", "ADD COLUMN `bank_card_no` varchar(64) DEFAULT NULL COMMENT '银行卡号' AFTER `alipay_account`"),
        ("bank_account_name", "ADD COLUMN `bank_account_name` varchar(64) DEFAULT NULL COMMENT '银行开户姓名' AFTER `bank_card_no`"),
        ("bank_name", "ADD COLUMN `bank_name` varchar(128) DEFAULT NULL COMMENT '开户银行' AFTER `bank_account_name`"),
    ]
    for col, ddl in additions:
        if not _column_exists(conn, 'commission_withdraw', col):
            conn.execute(text(f"ALTER TABLE `commission_withdraw` {ddl}"))
            logger.info(f"Added column commission_withdraw.{col}")
        else:
            logger.info(f"Column commission_withdraw.{col} already exists, skipping")


def downgrade() -> None:
    conn = op.get_bind()
    for col in ['bank_name', 'bank_account_name', 'bank_card_no', 'alipay_account', 'method']:
        if _column_exists(conn, 'commission_withdraw', col):
            conn.execute(text(f"ALTER TABLE `commission_withdraw` DROP COLUMN `{col}`"))
            logger.info(f"Dropped column commission_withdraw.{col}")
