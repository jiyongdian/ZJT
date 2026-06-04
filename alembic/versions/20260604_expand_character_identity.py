"""Expand character.identity from varchar(100) to text

角色身份描述字段过短，导致数据截断。将 identity 字段从 varchar(100) 扩展为 text 类型。

Revision ID: 20260604_char_identity
Revises: 20260604_image_retry
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260604_char_identity'
down_revision: Union[str, None] = '20260604_image_retry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将 character 表的 identity 字段从 varchar(100) 扩展为 text"""
    conn = op.get_bind()
    
    conn.execute(text("""
        ALTER TABLE `character`
        MODIFY COLUMN `identity` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '身份/职业'
    """))
    logger.info("[Migration] Expanded character.identity from varchar(100) to text")


def downgrade() -> None:
    """回滚：将 character 表的 identity 字段从 text 改回 varchar(100)"""
    conn = op.get_bind()
    
    # 注意：如果数据超过100字符，回滚会导致数据截断
    conn.execute(text("""
        ALTER TABLE `character`
        MODIFY COLUMN `identity` VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '身份/职业'
    """))
    logger.info("[Migration] Rolled back character.identity from text to varchar(100)")
