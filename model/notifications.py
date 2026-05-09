"""
Notifications Model - Database operations for notifications table
存储从远程服务器拉取的通知消息（版本更新、系统公告等）
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from .database import execute_query, execute_update, execute_insert
import logging

logger = logging.getLogger(__name__)


class NotificationEntity:
    """Notification database entity class"""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.remote_id = kwargs.get('remote_id')
        self.notification_type = kwargs.get('notification_type', 'announcement')
        self.title = kwargs.get('title', '')
        self.content = kwargs.get('content', '')
        self.level = kwargs.get('level', 'info')

        # Deserialize extra_data from JSON
        extra_json = kwargs.get('extra_data')
        if isinstance(extra_json, str) and extra_json:
            try:
                self.extra_data = json.loads(extra_json)
            except json.JSONDecodeError:
                self.extra_data = {}
        else:
            self.extra_data = extra_json or {}

        self.is_read = kwargs.get('is_read', 0)
        self.start_time = kwargs.get('start_time')
        self.end_time = kwargs.get('end_time')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API output"""
        return {
            'id': self.id,
            'remote_id': self.remote_id,
            'type': self.notification_type,
            'title': self.title,
            'content': self.content,
            'level': self.level,
            'link': self.extra_data.get('link'),
            'link_text': self.extra_data.get('link_text'),
            'is_read': bool(self.is_read),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class NotificationsModel:
    """Notifications database operations"""

    @staticmethod
    def create(
        remote_id: str,
        notification_type: str,
        title: str,
        content: str = '',
        level: str = 'info',
        extra_data: dict = None,
        start_time: str = None,
        end_time: str = None
    ) -> int:
        """
        Create a new notification (skip if remote_id already exists)

        Returns:
            Inserted record ID, or 0 if already exists
        """
        sql = """
            INSERT IGNORE INTO notifications
            (remote_id, notification_type, title, content, level, extra_data, start_time, end_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        extra_json = json.dumps(extra_data or {}, ensure_ascii=False)
        params = (remote_id, notification_type, title, content, level, extra_json, start_time, end_time)

        try:
            record_id = execute_insert(sql, params)
            if record_id > 0:
                logger.info(f"Created notification: {remote_id}")
            return record_id
        except Exception as e:
            logger.error(f"Failed to create notification: {e}")
            raise

    @staticmethod
    def get_unread(limit: int = 50) -> List[NotificationEntity]:
        """Get unread notifications that are currently valid"""
        sql = """
            SELECT * FROM notifications
            WHERE is_read = 0
              AND (start_time IS NULL OR start_time <= NOW())
              AND (end_time IS NULL OR end_time >= NOW())
            ORDER BY created_at DESC
            LIMIT %s
        """
        try:
            results = execute_query(sql, (limit,), fetch_all=True)
            return [NotificationEntity(**row) for row in (results or [])]
        except Exception as e:
            logger.error(f"Failed to get unread notifications: {e}")
            raise

    @staticmethod
    def get_unread_count() -> int:
        """Get count of unread valid notifications"""
        sql = """
            SELECT COUNT(*) as cnt FROM notifications
            WHERE is_read = 0
              AND (start_time IS NULL OR start_time <= NOW())
              AND (end_time IS NULL OR end_time >= NOW())
        """
        try:
            result = execute_query(sql, fetch_one=True)
            return result['cnt'] if result else 0
        except Exception as e:
            logger.error(f"Failed to get unread count: {e}")
            raise

    @staticmethod
    def mark_read(notification_id: int) -> int:
        """Mark a notification as read"""
        sql = "UPDATE notifications SET is_read = 1 WHERE id = %s"
        try:
            return execute_update(sql, (notification_id,))
        except Exception as e:
            logger.error(f"Failed to mark notification {notification_id} as read: {e}")
            raise

    @staticmethod
    def mark_all_read() -> int:
        """Mark all valid notifications as read"""
        sql = """
            UPDATE notifications SET is_read = 1
            WHERE is_read = 0
              AND (start_time IS NULL OR start_time <= NOW())
              AND (end_time IS NULL OR end_time >= NOW())
        """
        try:
            affected = execute_update(sql)
            if affected > 0:
                logger.info(f"Marked {affected} notifications as read")
            return affected
        except Exception as e:
            logger.error(f"Failed to mark all as read: {e}")
            raise

    @staticmethod
    def list_all(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List all notifications with pagination (admin use)"""
        offset = (page - 1) * page_size

        count_sql = "SELECT COUNT(*) as total FROM notifications"
        try:
            count_result = execute_query(count_sql, fetch_one=True)
            total = count_result['total'] if count_result else 0
        except Exception as e:
            logger.error(f"Failed to count notifications: {e}")
            raise

        sql = """
            SELECT * FROM notifications
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        try:
            results = execute_query(sql, (page_size, offset), fetch_all=True)
            items = [NotificationEntity(**row) for row in (results or [])]
            return {
                'items': items,
                'total': total,
                'page': page,
                'page_size': page_size,
            }
        except Exception as e:
            logger.error(f"Failed to list notifications: {e}")
            raise

    @staticmethod
    def delete_by_id(notification_id: int) -> int:
        """Delete a notification by ID"""
        sql = "DELETE FROM notifications WHERE id = %s"
        try:
            return execute_update(sql, (notification_id,))
        except Exception as e:
            logger.error(f"Failed to delete notification {notification_id}: {e}")
            raise

    @staticmethod
    def delete_expired() -> int:
        """Delete notifications that have passed their end_time"""
        sql = "DELETE FROM notifications WHERE end_time IS NOT NULL AND end_time < NOW()"
        try:
            affected = execute_update(sql)
            if affected > 0:
                logger.info(f"Deleted {affected} expired notifications")
            return affected
        except Exception as e:
            logger.error(f"Failed to delete expired notifications: {e}")
            raise


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `notifications` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `remote_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Remote notification ID (for dedup)',
  `notification_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'announcement' COMMENT 'Type: announcement/maintenance/feature/security',
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Notification title',
  `content` text COLLATE utf8mb4_unicode_ci COMMENT 'Notification content',
  `level` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'info' COMMENT 'Level: info/warning/error/success',
  `extra_data` text COLLATE utf8mb4_unicode_ci COMMENT 'Extra data JSON (link, link_text, etc)',
  `is_read` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Whether read by admin',
  `start_time` datetime DEFAULT NULL COMMENT 'Effective start time',
  `end_time` datetime DEFAULT NULL COMMENT 'Expiration time',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_remote_id` (`remote_id`),
  KEY `idx_is_read` (`is_read`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Remote server notifications'
"""
