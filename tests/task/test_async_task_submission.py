"""
AsyncTaskSubmission 纯逻辑单元测试

测试 _calculate_retry_delay 和 _get_driver_class 的纯逻辑行为。

只 mock model.database（不 mock model 包和 config.unified_config），
避免跨测试污染。
"""
import importlib
import sys
import unittest
from unittest.mock import MagicMock

# 保存原始模块引用，防止污染后续测试
_saved_model_database = sys.modules.get('model.database')

# 只 mock database 层，不 mock model 包本身
sys.modules['model.database'] = MagicMock()

# 如果模块已被加载（可能被其他测试用不同 mock 加载过），reload
for _mod in [
    'model.ai_tool_pipeline_steps', 'model.ai_tools', 'model.async_tasks',
    'model.runninghub_slots',
    'task.async_task_submission',
]:
    if _mod in sys.modules:
        importlib.reload(sys.modules[_mod])

from task.async_task_submission import _calculate_retry_delay, _get_driver_class

# 恢复 model.database，防止污染后续测试
if _saved_model_database is not None:
    sys.modules['model.database'] = _saved_model_database
else:
    sys.modules.pop('model.database', None)


class TestCalculateRetryDelay(unittest.TestCase):
    """测试 _calculate_retry_delay() 的指数退避逻辑"""

    def test_retry_count_0_returns_30(self):
        """第 0 次重试返回 30 秒"""
        self.assertEqual(_calculate_retry_delay(0), 30)

    def test_retry_count_1_returns_60(self):
        """第 1 次重试返回 60 秒"""
        self.assertEqual(_calculate_retry_delay(1), 60)

    def test_retry_count_2_returns_120(self):
        """第 2 次重试返回 120 秒"""
        self.assertEqual(_calculate_retry_delay(2), 120)

    def test_retry_count_3_returns_300(self):
        """第 3 次重试返回 300 秒"""
        self.assertEqual(_calculate_retry_delay(3), 300)

    def test_retry_count_4_returns_300(self):
        """第 4 次重试返回 300 秒（base_delays 的最后一个值）"""
        self.assertEqual(_calculate_retry_delay(4), 300)

    def test_retry_count_exceeds_returns_300(self):
        """超过 base_delays 长度时返回默认值 300 秒"""
        self.assertEqual(_calculate_retry_delay(10), 300)

    def test_retry_count_negative_returns_300(self):
        """负数索引访问 base_delays[-1]，Python 返回最后一个元素 300"""
        self.assertEqual(_calculate_retry_delay(-1), 300)


class TestGetDriverClass(unittest.TestCase):
    """测试 _get_driver_class() 的实现查找逻辑"""

    def test_unknown_impl_returns_none(self):
        """未知的 implementation id 返回 None"""
        result = _get_driver_class(999)
        self.assertIsNone(result)

    def test_none_impl_returns_none(self):
        """None 作为 impl_id 返回 None"""
        result = _get_driver_class(None)
        self.assertIsNone(result)

    def test_zero_impl_returns_none(self):
        """0 作为 impl_id 返回 None（不在 DRIVER_MAP 中）"""
        result = _get_driver_class(0)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
