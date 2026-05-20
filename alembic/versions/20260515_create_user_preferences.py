"""create_user_preferences

Revision ID: 20260515_user_prefs
Revises: 20260513_add_title
Create Date: 2026-05-15

Create user_preferences table for persisting user preference configs
(image/video ratio, resolution, text-to-image model selection)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260515_user_prefs'
down_revision: str = '20260513_add_title'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user_preferences table"""
    op.execute("""
        CREATE TABLE IF NOT EXISTS `user_preferences` (
          `id` int NOT NULL AUTO_INCREMENT,
          `user_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
          `world_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
          `pref_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'text_to_image_model|image_preferences|video_preferences',
          `config_value` json NOT NULL,
          `create_at` datetime DEFAULT CURRENT_TIMESTAMP,
          `update_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`),
          UNIQUE KEY `uk_user_pref` (`user_id`, `world_id`, `pref_type`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)


def downgrade() -> None:
    """Drop user_preferences table"""
    op.execute("DROP TABLE IF EXISTS `user_preferences`")
