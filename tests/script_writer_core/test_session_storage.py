"""
Session Storage 单元测试

测试 truncate_conversation_history 的纯逻辑。
"""
import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from script_writer_core.session_storage import truncate_conversation_history
from config.constant import SessionHistoryConstants


class TestTruncateConversationHistory(unittest.TestCase):
    """测试对话历史截断逻辑"""

    def test_no_truncation_needed(self):
        """消息数量未超过限制时不截断"""
        history = [
            {"role": "system", "content": "prompt"},
            {"role": "user", "content": "hi"},
        ]
        result = truncate_conversation_history(history, max_messages=10, keep_system=True)
        self.assertEqual(result, history)

    def test_truncate_with_system_keep(self):
        """保留 system 消息，截断普通消息（受 MIN_HISTORY_MESSAGES 保护）"""
        history = [{"role": "system", "content": "sys"}]
        history.extend([{"role": "user", "content": f"msg{i}"} for i in range(20)])
        result = truncate_conversation_history(history, max_messages=10, keep_system=True)
        # system + MIN_HISTORY_MESSAGES(10) 条普通消息 = 11 条
        self.assertEqual(len(result), 11)
        self.assertEqual(result[0]["role"], "system")
        self.assertEqual(result[1]["content"], "msg10")
        self.assertEqual(result[-1]["content"], "msg19")

    def test_truncate_without_system_keep(self):
        """不保留 system 消息，直接截断"""
        history = [{"role": "system", "content": "sys"}]
        history.extend([{"role": "user", "content": f"msg{i}"} for i in range(20)])
        result = truncate_conversation_history(history, max_messages=10, keep_system=False)
        self.assertEqual(len(result), 10)
        self.assertEqual(result[0]["content"], "msg10")
        self.assertEqual(result[-1]["content"], "msg19")

    def test_system_only_no_crash(self):
        """只有 system 消息时不崩溃"""
        history = [{"role": "system", "content": "sys"}]
        result = truncate_conversation_history(history, max_messages=5, keep_system=True)
        self.assertEqual(len(result), 1)

    def test_respect_min_history(self):
        """确保至少保留 MIN_HISTORY_MESSAGES 条普通消息"""
        history = [{"role": "system", "content": "sys"}]
        history.extend([{"role": "user", "content": f"msg{i}"} for i in range(5)])
        # max_messages=5, system=1, 理论上 max_other=4, 但总消息数不足 max_messages，不应截断
        result = truncate_conversation_history(history, max_messages=5, keep_system=True)
        self.assertEqual(len(result), 6)

    def test_multiple_system_messages(self):
        """多个 system 消息时全部保留（受 MIN_HISTORY_MESSAGES 保护）"""
        history = [
            {"role": "system", "content": "sys1"},
            {"role": "system", "content": "sys2"},
        ]
        history.extend([{"role": "user", "content": f"msg{i}"} for i in range(20)])
        result = truncate_conversation_history(history, max_messages=10, keep_system=True)
        # 2 system + MIN_HISTORY_MESSAGES(10) 条普通消息 = 12 条
        self.assertEqual(len(result), 12)
        self.assertEqual(result[0]["role"], "system")
        self.assertEqual(result[1]["role"], "system")

    def test_default_max_messages(self):
        """测试默认 max_messages"""
        history = [{"role": "user", "content": f"msg{i}"} for i in range(105)]
        result = truncate_conversation_history(history)
        self.assertLessEqual(len(result), SessionHistoryConstants.MAX_HISTORY_MESSAGES)

    def test_exact_limit(self):
        """测试刚好达到限制时不截断"""
        history = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        result = truncate_conversation_history(history, max_messages=10, keep_system=False)
        self.assertEqual(len(result), 10)

    def test_history_unchanged_when_under_limit(self):
        """测试未达限制时返回原列表（或等效副本）"""
        history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
        ]
        result = truncate_conversation_history(history, max_messages=100)
        self.assertEqual(len(result), 2)

    def test_empty_history(self):
        """测试空历史不崩溃"""
        result = truncate_conversation_history([], max_messages=10)
        self.assertEqual(result, [])

    def test_no_system_messages(self):
        """测试没有 system 消息时的截断"""
        history = [{"role": "user", "content": f"msg{i}"} for i in range(15)]
        result = truncate_conversation_history(history, max_messages=10, keep_system=True)
        self.assertEqual(len(result), 10)
        self.assertEqual(result[0]["content"], "msg5")
        self.assertEqual(result[-1]["content"], "msg14")


if __name__ == '__main__':
    unittest.main()
