"""backfill_workflow_ratio

Revision ID: 20260428_backfill_ratio
Revises: 20260427_workflow_ratio
Create Date: 2026-04-28 10:00:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20260428_backfill_ratio'
down_revision: Union[str, None] = '20260427_workflow_ratio'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """数据迁移：从 workflow_data JSON 中提取 ratio 回填到 workflow_ratio 字段"""
    op.execute("""
        UPDATE video_workflow
        SET workflow_ratio = JSON_UNQUOTE(JSON_EXTRACT(workflow_data, '$.ratio'))
        WHERE workflow_ratio IS NULL
          AND workflow_data IS NOT NULL
          AND JSON_EXTRACT(workflow_data, '$.ratio') IS NOT NULL
    """)


def downgrade() -> None:
    """数据迁移：回滚时不做操作（无法还原原始 NULL 状态）"""
    pass
