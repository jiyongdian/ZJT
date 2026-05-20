"""
Notifications CRUD 单元测试

测试 model/notifications.py 的实体和模型逻辑。
使用 mock 隔离数据库操作。
"""
import json
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from model.notifications import NotificationEntity, NotificationsModel


class TestNotificationEntity(unittest.TestCase):
    """测试 NotificationEntity 实体类"""

    def test_init_with_all_fields(self):
        entity = NotificationEntity(
            id=1,
            remote_id="notif-001",
            notification_type="announcement",
            title="Test Title",
            content="Test content",
            level="info",
            extra_data='{"link": "https://example.com", "link_text": "Click"}',
            is_read=0,
            start_time=datetime(2026, 1, 1),
            end_time=datetime(2026, 12, 31),
            created_at=datetime(2026, 5, 19),
            updated_at=datetime(2026, 5, 19),
        )
        self.assertEqual(entity.id, 1)
        self.assertEqual(entity.remote_id, "notif-001")
        self.assertEqual(entity.notification_type, "announcement")
        self.assertIsInstance(entity.extra_data, dict)
        self.assertEqual(entity.extra_data['link'], "https://example.com")

    def test_extra_data_json_parse(self):
        entity = NotificationEntity(extra_data='{"key": "value"}')
        self.assertEqual(entity.extra_data, {"key": "value"})

    def test_extra_data_invalid_json(self):
        entity = NotificationEntity(extra_data='not json')
        self.assertEqual(entity.extra_data, {})

    def test_extra_data_none(self):
        entity = NotificationEntity(extra_data=None)
        self.assertEqual(entity.extra_data, {})

    def test_extra_data_empty_string(self):
        entity = NotificationEntity(extra_data='')
        self.assertEqual(entity.extra_data, {})

    def test_extra_data_already_dict(self):
        entity = NotificationEntity(extra_data={"already": "dict"})
        self.assertEqual(entity.extra_data, {"already": "dict"})

    def test_defaults(self):
        entity = NotificationEntity()
        self.assertEqual(entity.notification_type, 'announcement')
        self.assertEqual(entity.title, '')
        self.assertEqual(entity.content, '')
        self.assertEqual(entity.level, 'info')
        self.assertEqual(entity.is_read, 0)
        self.assertEqual(entity.extra_data, {})

    def test_to_dict(self):
        now = datetime(2026, 5, 19, 10, 30, 0)
        entity = NotificationEntity(
            id=1,
            remote_id="r1",
            notification_type="feature",
            title="New Feature",
            content="Check it out",
            level="success",
            extra_data={"link": "https://example.com", "link_text": "Go"},
            is_read=0,
            start_time=now,
            end_time=now,
            created_at=now,
        )
        d = entity.to_dict()
        self.assertEqual(d['id'], 1)
        self.assertEqual(d['type'], "feature")
        self.assertEqual(d['title'], "New Feature")
        self.assertEqual(d['link'], "https://example.com")
        self.assertEqual(d['link_text'], "Go")
        self.assertFalse(d['is_read'])
        self.assertEqual(d['start_time'], "2026-05-19T10:30:00")
        self.assertEqual(d['created_at'], "2026-05-19T10:30:00")

    def test_to_dict_none_datetimes(self):
        entity = NotificationEntity(id=1)
        d = entity.to_dict()
        self.assertIsNone(d['start_time'])
        self.assertIsNone(d['end_time'])
        self.assertIsNone(d['created_at'])

    def test_to_dict_is_read_bool_conversion(self):
        entity = NotificationEntity(is_read=1)
        d = entity.to_dict()
        self.assertTrue(d['is_read'])

        entity2 = NotificationEntity(is_read=0)
        d2 = entity2.to_dict()
        self.assertFalse(d2['is_read'])

    def test_to_dict_missing_extra_data_fields(self):
        """extra_data 中没有 link 和 link_text 时返回 None"""
        entity = NotificationEntity(extra_data={})
        d = entity.to_dict()
        self.assertIsNone(d['link'])
        self.assertIsNone(d['link_text'])


class TestNotificationsModelCreate(unittest.TestCase):
    """测试 NotificationsModel.create"""

    @patch('model.notifications.execute_insert')
    def test_create_success(self, mock_insert):
        mock_insert.return_value = 1
        result = NotificationsModel.create(
            remote_id="notif-001",
            notification_type="announcement",
            title="Test",
            content="Content",
        )
        self.assertEqual(result, 1)

    @patch('model.notifications.execute_insert')
    def test_create_duplicate_returns_zero(self, mock_insert):
        mock_insert.return_value = 0  # INSERT IGNORE on duplicate
        result = NotificationsModel.create(
            remote_id="existing-id",
            notification_type="announcement",
            title="Duplicate",
        )
        self.assertEqual(result, 0)

    @patch('model.notifications.execute_insert')
    def test_create_with_extra_data(self, mock_insert):
        mock_insert.return_value = 1
        NotificationsModel.create(
            remote_id="notif-002",
            notification_type="feature",
            title="Feature",
            extra_data={"link": "https://example.com"},
        )
        # 验证 extra_data 被序列化
        call_args = mock_insert.call_args
        params = call_args[0][1]
        extra_parsed = json.loads(params[5])
        self.assertEqual(extra_parsed, {"link": "https://example.com"})

    @patch('model.notifications.execute_insert')
    def test_create_none_extra_data(self, mock_insert):
        mock_insert.return_value = 1
        NotificationsModel.create(
            remote_id="notif-003",
            notification_type="announcement",
            title="No Extra",
            extra_data=None,
        )
        call_args = mock_insert.call_args
        params = call_args[0][1]
        self.assertEqual(params[5], '{}')


class TestNotificationsModelGetUnread(unittest.TestCase):
    """测试 NotificationsModel.get_unread"""

    @patch('model.notifications.execute_query')
    def test_returns_entities(self, mock_query):
        mock_query.return_value = [
            {'id': 1, 'remote_id': 'r1', 'notification_type': 'announcement',
             'title': 'T1', 'content': 'C1', 'level': 'info', 'extra_data': '{}',
             'is_read': 0, 'start_time': None, 'end_time': None,
             'created_at': datetime.now(), 'updated_at': None},
        ]
        result = NotificationsModel.get_unread()
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], NotificationEntity)

    @patch('model.notifications.execute_query')
    def test_returns_empty_list(self, mock_query):
        mock_query.return_value = None
        result = NotificationsModel.get_unread()
        self.assertEqual(result, [])


class TestNotificationsModelGetUnreadCount(unittest.TestCase):
    """测试 NotificationsModel.get_unread_count"""

    @patch('model.notifications.execute_query')
    def test_has_unread(self, mock_query):
        mock_query.return_value = {'cnt': 5}
        result = NotificationsModel.get_unread_count()
        self.assertEqual(result, 5)

    @patch('model.notifications.execute_query')
    def test_no_unread(self, mock_query):
        mock_query.return_value = {'cnt': 0}
        result = NotificationsModel.get_unread_count()
        self.assertEqual(result, 0)

    @patch('model.notifications.execute_query')
    def test_no_result(self, mock_query):
        mock_query.return_value = None
        result = NotificationsModel.get_unread_count()
        self.assertEqual(result, 0)


class TestNotificationsModelMarkRead(unittest.TestCase):
    """测试 NotificationsModel.mark_read"""

    @patch('model.notifications.execute_update')
    def test_mark_read_success(self, mock_update):
        mock_update.return_value = 1
        result = NotificationsModel.mark_read(1)
        self.assertEqual(result, 1)

    @patch('model.notifications.execute_update')
    def test_mark_read_not_found(self, mock_update):
        mock_update.return_value = 0
        result = NotificationsModel.mark_read(999)
        self.assertEqual(result, 0)


class TestNotificationsModelMarkAllRead(unittest.TestCase):
    """测试 NotificationsModel.mark_all_read"""

    @patch('model.notifications.execute_update')
    def test_mark_all_read(self, mock_update):
        mock_update.return_value = 3
        result = NotificationsModel.mark_all_read()
        self.assertEqual(result, 3)

    @patch('model.notifications.execute_update')
    def test_no_unread(self, mock_update):
        mock_update.return_value = 0
        result = NotificationsModel.mark_all_read()
        self.assertEqual(result, 0)


class TestNotificationsModelListAll(unittest.TestCase):
    """测试 NotificationsModel.list_all"""

    @patch('model.notifications.execute_query')
    def test_list_with_results(self, mock_query):
        mock_query.side_effect = [
            {'total': 2},  # count query
            [  # list query
                {'id': 1, 'remote_id': 'r1', 'notification_type': 'announcement',
                 'title': 'T1', 'content': 'C1', 'level': 'info', 'extra_data': '{}',
                 'is_read': 0, 'start_time': None, 'end_time': None,
                 'created_at': datetime.now(), 'updated_at': None},
                {'id': 2, 'remote_id': 'r2', 'notification_type': 'feature',
                 'title': 'T2', 'content': 'C2', 'level': 'success', 'extra_data': '{}',
                 'is_read': 1, 'start_time': None, 'end_time': None,
                 'created_at': datetime.now(), 'updated_at': None},
            ]
        ]
        result = NotificationsModel.list_all(page=1, page_size=20)
        self.assertEqual(result['total'], 2)
        self.assertEqual(len(result['items']), 2)
        self.assertEqual(result['page'], 1)
        self.assertEqual(result['page_size'], 20)

    @patch('model.notifications.execute_query')
    def test_list_empty(self, mock_query):
        mock_query.side_effect = [
            {'total': 0},
            None,
        ]
        result = NotificationsModel.list_all(page=1, page_size=20)
        self.assertEqual(result['total'], 0)
        self.assertEqual(result['items'], [])

    @patch('model.notifications.execute_query')
    def test_pagination_offset(self, mock_query):
        mock_query.side_effect = [{'total': 50}, None]
        NotificationsModel.list_all(page=3, page_size=10)
        # 验证 LIMIT 和 OFFSET 参数
        list_call = mock_query.call_args_list[1]
        self.assertEqual(list_call[0][1], (10, 20))  # page_size=10, offset=(3-1)*10=20


class TestNotificationsModelDelete(unittest.TestCase):
    """测试 NotificationsModel.delete_by_id 和 delete_expired"""

    @patch('model.notifications.execute_update')
    def test_delete_by_id_success(self, mock_update):
        mock_update.return_value = 1
        result = NotificationsModel.delete_by_id(1)
        self.assertEqual(result, 1)

    @patch('model.notifications.execute_update')
    def test_delete_by_id_not_found(self, mock_update):
        mock_update.return_value = 0
        result = NotificationsModel.delete_by_id(999)
        self.assertEqual(result, 0)

    @patch('model.notifications.execute_update')
    def test_delete_expired(self, mock_update):
        mock_update.return_value = 5
        result = NotificationsModel.delete_expired()
        self.assertEqual(result, 5)

    @patch('model.notifications.execute_update')
    def test_delete_expired_none(self, mock_update):
        mock_update.return_value = 0
        result = NotificationsModel.delete_expired()
        self.assertEqual(result, 0)


if __name__ == '__main__':
    unittest.main()
