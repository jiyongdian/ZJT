"""
会话清理任务单元测试

测试 task/session_cleanup.py 的清理逻辑。
使用 mock 隔离数据库和文件系统。
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)


class TestCleanupExpiredSessions(unittest.TestCase):
    """测试 cleanup_expired_sessions"""

    @patch('task.session_cleanup.ChatSessionsModel')
    @patch('task.session_cleanup._cleanup_orphan_marketing_images')
    def test_returns_deleted_count(self, mock_cleanup_orphans, mock_model):
        """正常清理返回删除数量"""
        mock_model.delete_expired_sessions.return_value = 5
        from task.session_cleanup import cleanup_expired_sessions
        result = cleanup_expired_sessions()
        self.assertEqual(result, 5)

    @patch('task.session_cleanup.ChatSessionsModel')
    @patch('task.session_cleanup._cleanup_orphan_marketing_images')
    def test_no_expired_sessions(self, mock_cleanup_orphans, mock_model):
        """无过期会话返回 0"""
        mock_model.delete_expired_sessions.return_value = 0
        from task.session_cleanup import cleanup_expired_sessions
        result = cleanup_expired_sessions()
        self.assertEqual(result, 0)

    @patch('task.session_cleanup.ChatSessionsModel')
    @patch('task.session_cleanup._cleanup_orphan_marketing_images')
    def test_db_error_returns_zero(self, mock_cleanup_orphans, mock_model):
        """数据库异常不抛出，返回 0"""
        mock_model.delete_expired_sessions.side_effect = Exception("DB error")
        from task.session_cleanup import cleanup_expired_sessions
        result = cleanup_expired_sessions()
        self.assertEqual(result, 0)

    @patch('task.session_cleanup.ChatSessionsModel')
    @patch('task.session_cleanup._cleanup_orphan_marketing_images')
    def test_orphan_cleanup_failure_does_not_affect_main(self, mock_cleanup_orphans, mock_model):
        """孤立图片清理失败不影响主流程"""
        mock_model.delete_expired_sessions.return_value = 3
        mock_cleanup_orphans.side_effect = Exception("cleanup failed")
        from task.session_cleanup import cleanup_expired_sessions
        result = cleanup_expired_sessions()
        self.assertEqual(result, 3)


class TestCleanupOrphanMarketingImages(unittest.TestCase):
    """测试 _cleanup_orphan_marketing_images"""

    @patch('task.session_cleanup.os.path.isdir', return_value=False)
    @patch('task.session_cleanup.ChatSessionsModel')
    def test_base_dir_not_exists(self, mock_model, mock_isdir):
        """基础目录不存在时直接返回"""
        from task.session_cleanup import _cleanup_orphan_marketing_images
        _cleanup_orphan_marketing_images()
        mock_model.session_exists.assert_not_called()

    @patch('task.session_cleanup.shutil.rmtree')
    @patch('task.session_cleanup.ChatSessionsModel')
    @patch('task.session_cleanup.os.path.isdir')
    @patch('task.session_cleanup.os.listdir')
    def test_removes_orphan_dirs(self, mock_listdir, mock_isdir, mock_model, mock_rmtree):
        """删除数据库中不存在的 session 目录"""
        # 基础目录存在，子目录也是目录
        mock_isdir.side_effect = [True, True, True]  # base_dir, entry1, entry2
        mock_listdir.return_value = ['session-001', 'session-002']

        # session-001 不存在（孤立），session-002 存在
        mock_model.session_exists.side_effect = [False, True]

        from task.session_cleanup import _cleanup_orphan_marketing_images
        _cleanup_orphan_marketing_images()

        # 只删除孤立的
        mock_rmtree.assert_called_once()

    @patch('task.session_cleanup.shutil.rmtree')
    @patch('task.session_cleanup.ChatSessionsModel')
    @patch('task.session_cleanup.os.path.isdir')
    @patch('task.session_cleanup.os.listdir')
    def test_skips_non_directory_entries(self, mock_listdir, mock_isdir, mock_model, mock_rmtree):
        """跳过非目录条目（文件等）"""
        mock_isdir.side_effect = [True, False]  # base_dir=True, entry=False (file)
        mock_listdir.return_value = ['somefile.txt']

        from task.session_cleanup import _cleanup_orphan_marketing_images
        _cleanup_orphan_marketing_images()

        mock_model.session_exists.assert_not_called()
        mock_rmtree.assert_not_called()

    @patch('task.session_cleanup.shutil.rmtree')
    @patch('task.session_cleanup.ChatSessionsModel')
    @patch('task.session_cleanup.os.path.isdir')
    @patch('task.session_cleanup.os.listdir')
    def test_session_check_error_skips_entry(self, mock_listdir, mock_isdir, mock_model, mock_rmtree):
        """session 检查异常时跳过该条目"""
        mock_isdir.side_effect = [True, True]
        mock_listdir.return_value = ['session-error']
        mock_model.session_exists.side_effect = Exception("DB error")

        from task.session_cleanup import _cleanup_orphan_marketing_images
        _cleanup_orphan_marketing_images()

        mock_rmtree.assert_not_called()

    @patch('task.session_cleanup.shutil.rmtree', side_effect=PermissionError("denied"))
    @patch('task.session_cleanup.ChatSessionsModel')
    @patch('task.session_cleanup.os.path.isdir')
    @patch('task.session_cleanup.os.listdir')
    def test_rmtree_failure_does_not_stop(self, mock_listdir, mock_isdir, mock_model, mock_rmtree):
        """删除目录失败不中断后续处理"""
        mock_isdir.side_effect = [True, True, True]
        mock_listdir.return_value = ['session-001', 'session-002']
        mock_model.session_exists.side_effect = [False, False]

        from task.session_cleanup import _cleanup_orphan_marketing_images
        # 不应抛出异常
        _cleanup_orphan_marketing_images()

        # 应尝试删除两个
        self.assertEqual(mock_rmtree.call_count, 2)

    @patch('task.session_cleanup.os.path.isdir', return_value=False)
    @patch('task.session_cleanup.os.listdir', side_effect=PermissionError("denied"))
    @patch('task.session_cleanup.ChatSessionsModel')
    def test_listdir_failure_returns_gracefully(self, mock_model, mock_listdir, mock_isdir):
        """listdir 失败时安全返回"""
        mock_isdir.return_value = True

        from task.session_cleanup import _cleanup_orphan_marketing_images
        # 不应抛出异常
        _cleanup_orphan_marketing_images()


if __name__ == '__main__':
    unittest.main()
