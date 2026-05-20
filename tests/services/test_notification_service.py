"""
通知服务单元测试

测试 NotificationService 中的纯函数和轻依赖逻辑：
_compare_version、_process_response、_generate_client_id
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from services.notification_service import NotificationService


class TestCompareVersion(unittest.TestCase):
    """测试版本号比较逻辑"""

    def test_equal_versions(self):
        self.assertEqual(NotificationService._compare_version("1.2.3", "1.2.3"), 0)
        self.assertEqual(NotificationService._compare_version("v1.2.3", "1.2.3"), 0)

    def test_greater_version(self):
        self.assertEqual(NotificationService._compare_version("1.2.4", "1.2.3"), 1)
        self.assertEqual(NotificationService._compare_version("1.3.0", "1.2.9"), 1)
        self.assertEqual(NotificationService._compare_version("2.0.0", "1.9.9"), 1)

    def test_lesser_version(self):
        self.assertEqual(NotificationService._compare_version("1.2.2", "1.2.3"), -1)
        self.assertEqual(NotificationService._compare_version("1.1.9", "1.2.0"), -1)
        self.assertEqual(NotificationService._compare_version("0.9.9", "1.0.0"), -1)

    def test_different_length(self):
        # 短版本号在长度不同时被视为更小
        self.assertEqual(NotificationService._compare_version("1.2", "1.2.0"), -1)
        self.assertEqual(NotificationService._compare_version("1.2.3", "1.2"), 1)
        self.assertEqual(NotificationService._compare_version("1.0", "1.0.1"), -1)

    def test_prerelease_ignored(self):
        """预发布标签应被忽略（只比较主版本号）"""
        self.assertEqual(NotificationService._compare_version("1.2.3-beta", "1.2.3"), 0)
        self.assertEqual(NotificationService._compare_version("1.2.3-beta", "1.2.4"), -1)

    def test_invalid_parts_treated_as_zero(self):
        """非数字部分应被当作 0"""
        self.assertEqual(NotificationService._compare_version("1.x.3", "1.0.3"), 0)
        self.assertEqual(NotificationService._compare_version("1.a.b", "1.0.0"), 0)


class TestProcessResponse(unittest.TestCase):
    """测试 _process_response 方法"""

    def setUp(self):
        # 重置类状态
        NotificationService._version_status = {}
        NotificationService._required_binaries = []
        NotificationService._check_interval = 3600
        NotificationService._local_version = "1.0.0"

    def tearDown(self):
        NotificationService._version_status = {}
        NotificationService._required_binaries = []
        NotificationService._check_interval = 3600
        NotificationService._local_version = None

    def test_version_update(self):
        """测试版本更新信息处理"""
        data = {
            "version_update": {
                "has_update": True,
                "latest_version": "1.1.0",
                "release_notes": "新功能",
                "changelog_url": "https://example.com/changelog"
            }
        }
        NotificationService._process_response(data)
        self.assertTrue(NotificationService._version_status["has_update"])
        self.assertEqual(NotificationService._version_status["latest_version"], "1.1.0")
        self.assertEqual(NotificationService._version_status["current_version"], "1.0.0")

    def test_check_interval_update(self):
        """测试检查间隔更新"""
        data = {"check_interval": 1800}
        NotificationService._process_response(data)
        self.assertEqual(NotificationService._check_interval, 1800)

    def test_invalid_check_interval_ignored(self):
        """测试无效的检查间隔被忽略"""
        original = NotificationService._check_interval
        data = {"check_interval": -1}
        NotificationService._process_response(data)
        self.assertEqual(NotificationService._check_interval, original)

        data = {"check_interval": "not_int"}
        NotificationService._process_response(data)
        self.assertEqual(NotificationService._check_interval, original)

    def test_zero_check_interval_ignored(self):
        """测试 0 检查间隔被忽略"""
        original = NotificationService._check_interval
        data = {"check_interval": 0}
        NotificationService._process_response(data)
        self.assertEqual(NotificationService._check_interval, original)

    @patch('model.notifications.NotificationsModel')
    def test_announcements_saved(self, mock_model):
        """测试公告存入数据库"""
        mock_model.create.return_value = 1
        data = {
            "announcements": [
                {
                    "id": "ann-1",
                    "type": "announcement",
                    "title": "公告标题",
                    "content": "公告内容",
                    "level": "info",
                    "link": "https://example.com",
                    "link_text": "点击查看"
                }
            ]
        }
        NotificationService._process_response(data)
        mock_model.create.assert_called_once()
        call_kwargs = mock_model.create.call_args.kwargs
        self.assertEqual(call_kwargs['remote_id'], 'ann-1')
        self.assertEqual(call_kwargs['title'], '公告标题')
        self.assertEqual(call_kwargs['extra_data'], {"link": "https://example.com", "link_text": "点击查看"})

    @patch('model.notifications.NotificationsModel')
    def test_announcement_without_link(self, mock_model):
        """测试没有链接的公告 extra_data 为 None"""
        mock_model.create.return_value = 1
        data = {
            "announcements": [
                {
                    "id": "ann-1",
                    "title": "简单公告",
                    "content": "内容"
                }
            ]
        }
        NotificationService._process_response(data)
        call_kwargs = mock_model.create.call_args.kwargs
        self.assertIsNone(call_kwargs['extra_data'])

    @patch('model.notifications.NotificationsModel')
    def test_announcement_without_id_skipped(self, mock_model):
        """测试没有 id 的公告被跳过"""
        data = {
            "announcements": [
                {"title": "无ID", "content": "内容"}
            ]
        }
        NotificationService._process_response(data)
        mock_model.create.assert_not_called()

    @patch('model.notifications.NotificationsModel')
    def test_multiple_announcements(self, mock_model):
        """测试多个公告的处理"""
        mock_model.create.return_value = 1
        data = {
            "announcements": [
                {"id": "1", "title": "A", "content": "a"},
                {"id": "2", "title": "B", "content": "b"},
            ]
        }
        NotificationService._process_response(data)
        self.assertEqual(mock_model.create.call_count, 2)

    def test_empty_response(self):
        """测试空响应不报错"""
        NotificationService._process_response({})
        self.assertEqual(NotificationService._version_status, {})


class TestGenerateClientId(unittest.TestCase):
    """测试客户端 ID 生成"""

    @patch('platform.node', return_value='test-host')
    @patch('socket.gethostbyname', return_value='192.168.1.1')
    def test_generate_consistent_id(self, mock_gethost, mock_node):
        """测试相同输入产生相同 ID"""
        project_dir = Path('/fake/project')
        id1 = NotificationService._generate_client_id(project_dir)
        id2 = NotificationService._generate_client_id(project_dir)
        self.assertEqual(id1, id2)
        self.assertEqual(len(id1), 32)

    @patch('platform.node', return_value='host-a')
    @patch('socket.gethostbyname', return_value='10.0.0.1')
    def test_different_host_different_id(self, mock_gethost, mock_node):
        """测试不同主机产生不同 ID"""
        project_dir = Path('/fake/project')
        id_a = NotificationService._generate_client_id(project_dir)

        with patch('platform.node', return_value='host-b'):
            with patch('socket.gethostbyname', return_value='10.0.0.2'):
                id_b = NotificationService._generate_client_id(project_dir)

        self.assertNotEqual(id_a, id_b)

    @patch('platform.node', side_effect=Exception('fail'))
    @patch('socket.gethostbyname', side_effect=Exception('fail'))
    def test_fallback_on_error(self, mock_gethost, mock_node):
        """测试异常时仍然能生成 ID"""
        cid = NotificationService._generate_client_id()
        self.assertEqual(len(cid), 32)
        # 确保不是空字符串
        self.assertTrue(len(cid.strip()) > 0)


class TestGetVersionStatus(unittest.TestCase):
    """测试版本状态获取"""

    def test_returns_copy(self):
        """测试返回的是副本，修改不影响原数据"""
        NotificationService._version_status = {"has_update": True}
        result = NotificationService.get_version_status()
        result["has_update"] = False
        self.assertTrue(NotificationService._version_status["has_update"])


if __name__ == '__main__':
    unittest.main()
