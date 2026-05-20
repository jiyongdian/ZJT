"""
UserPreferences CRUD 单元测试

测试 model/user_preferences.py 的实体和模型逻辑。
使用 mock 隔离数据库操作。
"""
import json
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from model.user_preferences import UserPreference, UserPreferencesModel


class TestUserPreferenceEntity(unittest.TestCase):
    """测试 UserPreference 实体类"""

    def test_init_with_all_fields(self):
        now = datetime.now()
        pref = UserPreference(
            id=1,
            user_id="user1",
            world_id="world1",
            pref_type="text_to_image_model",
            config_value='{"model": "gpt_image_2"}',
            create_at=now,
            update_at=now,
        )
        self.assertEqual(pref.id, 1)
        self.assertEqual(pref.user_id, "user1")
        self.assertEqual(pref.pref_type, "text_to_image_model")

    def test_init_with_defaults(self):
        pref = UserPreference()
        self.assertIsNone(pref.id)
        self.assertIsNone(pref.user_id)
        self.assertIsNone(pref.config_value)

    def test_get_value_none(self):
        pref = UserPreference(config_value=None)
        self.assertIsNone(pref.get_value())

    def test_get_value_valid_json(self):
        pref = UserPreference(config_value='{"key": "value"}')
        result = pref.get_value()
        self.assertEqual(result, {"key": "value"})

    def test_get_value_invalid_json(self):
        pref = UserPreference(config_value="not json at all")
        result = pref.get_value()
        self.assertEqual(result, "not json at all")

    def test_get_value_already_dict(self):
        pref = UserPreference(config_value={"already": "dict"})
        result = pref.get_value()
        self.assertEqual(result, {"already": "dict"})

    def test_get_value_list(self):
        pref = UserPreference(config_value=[1, 2, 3])
        result = pref.get_value()
        self.assertEqual(result, [1, 2, 3])

    def test_to_dict(self):
        now = datetime(2026, 5, 19, 12, 0, 0)
        pref = UserPreference(
            id=1,
            user_id="user1",
            world_id="world1",
            pref_type="test",
            config_value='{"k": "v"}',
            create_at=now,
            update_at=now,
        )
        d = pref.to_dict()
        self.assertEqual(d['id'], 1)
        self.assertEqual(d['user_id'], "user1")
        self.assertEqual(d['config_value'], {"k": "v"})
        self.assertEqual(d['create_at'], "2026-05-19T12:00:00")
        self.assertEqual(d['update_at'], "2026-05-19T12:00:00")

    def test_to_dict_none_datetimes(self):
        pref = UserPreference(id=1, user_id="u", world_id="w", pref_type="t")
        d = pref.to_dict()
        self.assertIsNone(d['create_at'])
        self.assertIsNone(d['update_at'])


class TestUserPreferencesModelGet(unittest.TestCase):
    """测试 UserPreferencesModel.get"""

    @patch('model.user_preferences.execute_query')
    def test_found(self, mock_query):
        mock_query.return_value = {
            'id': 1, 'user_id': 'u1', 'world_id': 'w1',
            'pref_type': 'test', 'config_value': '{"a": 1}',
            'create_at': None, 'update_at': None
        }
        result = UserPreferencesModel.get("u1", "w1", "test")
        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, "u1")
        self.assertIsInstance(result, UserPreference)

    @patch('model.user_preferences.execute_query')
    def test_not_found(self, mock_query):
        mock_query.return_value = None
        result = UserPreferencesModel.get("u1", "w1", "nonexistent")
        self.assertIsNone(result)


class TestUserPreferencesModelUpsert(unittest.TestCase):
    """测试 UserPreferencesModel.upsert"""

    @patch('model.user_preferences.execute_update')
    def test_upsert_returns_result(self, mock_update):
        mock_update.return_value = 1
        result = UserPreferencesModel.upsert("u1", "w1", "test", {"model": "gpt_image_2"})
        self.assertEqual(result, 1)
        # 验证传入了 JSON 序列化的值
        call_args = mock_update.call_args
        self.assertIn('"model"', call_args[0][1][3])  # config_value parameter

    @patch('model.user_preferences.execute_update')
    def test_upsert_dict_value(self, mock_update):
        mock_update.return_value = 2
        UserPreferencesModel.upsert("u1", "w1", "test", {"nested": {"key": "val"}})
        call_args = mock_update.call_args
        config_val = call_args[0][1][3]
        parsed = json.loads(config_val)
        self.assertEqual(parsed, {"nested": {"key": "val"}})


class TestUserPreferencesModelDelete(unittest.TestCase):
    """测试 UserPreferencesModel.delete"""

    @patch('model.user_preferences.execute_update')
    def test_delete_existing(self, mock_update):
        mock_update.return_value = 1
        result = UserPreferencesModel.delete("u1", "w1", "test")
        self.assertTrue(result)

    @patch('model.user_preferences.execute_update')
    def test_delete_nonexistent(self, mock_update):
        mock_update.return_value = 0
        result = UserPreferencesModel.delete("u1", "w1", "nonexistent")
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
