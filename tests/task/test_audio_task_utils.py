"""
audio_task 纯函数单元测试

测试 build_character_audio_text 和 calculate_next_retry_delay。
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock 所有 task/audio_task.py 的重依赖
_saved_model = sys.modules.get('model')
_saved_config_constant = sys.modules.get('config.constant')
_saved_config_util = sys.modules.get('config.config_util')
_saved_rh_config = sys.modules.get('task.async_drivers.runninghub_audio_driver')
_saved_index_tts = sys.modules.get('utils.index_tts_util')

sys.modules['model'] = MagicMock()
sys.modules['model'].__dict__.update({
    'TasksModel': MagicMock(),
    'AIAudioModel': MagicMock(),
})
# 需要在 model 包存在后再 mock 子模块
import types
model_pkg = types.ModuleType('model')
model_pkg.TasksModel = MagicMock()
model_pkg.AIAudioModel = MagicMock()
sys.modules['model'] = model_pkg

# Mock config.constant
config_constant = types.ModuleType('config.constant')
config_constant.TASK_TYPE_GENERATE_AUDIO = 10
config_constant.AI_AUDIO_STATUS_PENDING = 0
config_constant.AI_AUDIO_STATUS_PROCESSING = 1
config_constant.AI_AUDIO_STATUS_COMPLETED = 2
config_constant.AI_AUDIO_STATUS_FAILED = -1
config_constant.TASK_STATUS_QUEUED = 0
config_constant.TASK_STATUS_PROCESSING = 1
config_constant.TASK_STATUS_COMPLETED = 2
config_constant.TASK_STATUS_FAILED = -1
sys.modules['config.constant'] = config_constant

# Mock RunningHubAudioConfig
rh_config = types.ModuleType('task.async_drivers.runninghub_audio_driver')
rh_config.RunningHubAudioConfig = MagicMock()
rh_config.RunningHubAudioConfig.AUDIO_STYLE_DEFAULT_PROMPT = '声音自然清晰，语气平稳，适合角色旁白'
rh_config.RunningHubAudioConfig.AUDIO_STYLE_LLM_MAX_TOKENS = 256
rh_config.RunningHubAudioConfig.AUDIO_STYLE_LLM_TEMPERATURE = 0.7
sys.modules['task.async_drivers.runninghub_audio_driver'] = rh_config

sys.modules['utils.index_tts_util'] = MagicMock()
sys.modules['config.config_util'] = MagicMock()

from task.audio_task import build_character_audio_text, calculate_next_retry_delay, _extract_gender_from_text

# 恢复被 mock 的 sys.modules，防止污染后续测试
for _key, _saved in [
    ('model', _saved_model),
    ('config.constant', _saved_config_constant),
    ('config.config_util', _saved_config_util),
    ('task.async_drivers.runninghub_audio_driver', _saved_rh_config),
    ('utils.index_tts_util', _saved_index_tts),
]:
    if _saved is not None:
        sys.modules[_key] = _saved
    else:
        sys.modules.pop(_key, None)


class TestBuildCharacterAudioText(unittest.TestCase):
    """测试 build_character_audio_text()"""

    def test_custom_text_takes_priority(self):
        """自定义文本优先返回"""
        result = build_character_audio_text(
            character_data={"name": "Alice"},
            custom_text="这是自定义的音频文本"
        )
        self.assertEqual(result, "这是自定义的音频文本")

    def test_custom_text_with_whitespace(self):
        """自定义文本会被 strip"""
        result = build_character_audio_text(
            character_data={"name": "Alice"},
            custom_text="  有内容的文本  "
        )
        self.assertEqual(result, "有内容的文本")

    def test_empty_custom_text_uses_default_format(self):
        """空 custom_text 时使用默认模板"""
        result = build_character_audio_text(
            character_data={"name": "张三", "identity": "勇士"},
            custom_text=""
        )
        self.assertEqual(result, "大家好，我是张三，是勇士。很高兴在这个故事里与你相遇。")

    def test_with_age_and_male_gender(self):
        """包含年龄和男性性别信息"""
        result = build_character_audio_text(
            character_data={"name": "张伟", "age": "30", "identity": "程序员", "appearance": "一位高大的男性"},
            custom_text=None
        )
        self.assertEqual(result, "大家好，我是张伟，今年30岁，是一位男性，是程序员。很高兴在这个故事里与你相遇。")

    def test_with_age_and_female_gender(self):
        """包含年龄和女性性别信息"""
        result = build_character_audio_text(
            character_data={"name": "小美", "age": "25", "identity": "公主", "appearance": "美丽的女子"},
            custom_text=None
        )
        self.assertEqual(result, "大家好，我是小美，今年25岁，是一位女性，是公主。很高兴在这个故事里与你相遇。")

    def test_with_age_no_gender(self):
        """包含年龄但无性别信息"""
        result = build_character_audio_text(
            character_data={"name": "冒险者", "age": "20", "identity": "冒险者"},
            custom_text=None
        )
        self.assertEqual(result, "大家好，我是冒险者，今年20岁，是冒险者。很高兴在这个故事里与你相遇。")

    def test_with_gender_no_age(self):
        """包含性别但无年龄信息"""
        result = build_character_audio_text(
            character_data={"name": "少年", "identity": "少年", "appearance": "英俊的男孩"},
            custom_text=None
        )
        self.assertEqual(result, "大家好，我是少年，是一位男性，是少年。很高兴在这个故事里与你相遇。")

    def test_no_age_no_gender(self):
        """无年龄无性别信息"""
        result = build_character_audio_text(
            character_data={"name": "神秘人", "identity": "神秘人"},
            custom_text=None
        )
        self.assertEqual(result, "大家好，我是神秘人，是神秘人。很高兴在这个故事里与你相遇。")

    def test_none_custom_text(self):
        """None custom_text 时使用默认模板"""
        result = build_character_audio_text(
            character_data={"name": "李四", "identity": "法师"},
            custom_text=None
        )
        self.assertEqual(result, "大家好，我是李四，是法师。很高兴在这个故事里与你相遇。")

    def test_no_name_falls_back_to_default(self):
        """无角色名时 fallback 为 '我'"""
        result = build_character_audio_text(
            character_data={"identity": "战士"},
            custom_text=None
        )
        self.assertIn("我是我", result)
        self.assertIn("是战士", result)

    def test_no_identity_falls_back_to_default(self):
        """无身份时 fallback 为 '故事中的角色'"""
        result = build_character_audio_text(
            character_data={"name": "王五"},
            custom_text=None
        )
        self.assertIn("故事中的角色", result)
        self.assertIn("我是王五", result)

    def test_no_character_data_at_all(self):
        """完全无角色数据时使用所有默认值"""
        result = build_character_audio_text(
            character_data={},
            custom_text=None
        )
        self.assertEqual(result, "大家好，我是我，是故事中的角色。很高兴在这个故事里与你相遇。")

    def test_extract_gender_from_text_male(self):
        """从文本中提取男性性别信息"""
        self.assertEqual(_extract_gender_from_text("程序员 一位高大的男性"), "男性")
        self.assertEqual(_extract_gender_from_text("少年"), "男性")
        self.assertEqual(_extract_gender_from_text("先生"), "男性")
        self.assertEqual(_extract_gender_from_text("父亲"), "男性")

    def test_extract_gender_from_text_female(self):
        """从文本中提取女性性别信息"""
        self.assertEqual(_extract_gender_from_text("公主 美丽的女子"), "女性")
        self.assertEqual(_extract_gender_from_text("小姐"), "女性")
        self.assertEqual(_extract_gender_from_text("母亲"), "女性")
        self.assertEqual(_extract_gender_from_text("皇后"), "女性")

    def test_extract_gender_from_text_no_gender(self):
        """无性别信息时返回空字符串"""
        self.assertEqual(_extract_gender_from_text("冒险者"), "")
        self.assertEqual(_extract_gender_from_text("神秘人"), "")
        self.assertEqual(_extract_gender_from_text(""), "")

    def test_whitespace_only_custom_text_ignored(self):
        """仅含空格的 custom_text 被视为空"""
        result = build_character_audio_text(
            character_data={"name": "测试", "identity": "角色"},
            custom_text="   "
        )
        self.assertIn("我是测试", result)


class TestCalculateNextRetryDelay(unittest.TestCase):
    """测试 calculate_next_retry_delay()"""

    def test_first_retry(self):
        """第 1 次重试：3 * 2^0 = 3s"""
        self.assertEqual(calculate_next_retry_delay(1), 3)

    def test_second_retry(self):
        """第 2 次重试：3 * 2^1 = 6s"""
        self.assertEqual(calculate_next_retry_delay(2), 6)

    def test_third_retry(self):
        """第 3 次重试：3 * 2^2 = 12s"""
        self.assertEqual(calculate_next_retry_delay(3), 12)

    def test_fifth_retry(self):
        """第 5 次重试：3 * 2^4 = 48s"""
        self.assertEqual(calculate_next_retry_delay(5), 48)

    def test_seventh_retry(self):
        """第 7 次重试：3 * 2^6 = 192s"""
        self.assertEqual(calculate_next_retry_delay(7), 192)

    def test_capped_at_max_delay(self):
        """超过 360s 时截断"""
        # 3 * 2^7 = 384 > 360
        self.assertEqual(calculate_next_retry_delay(8), 360)

    def test_high_retry_count_still_capped(self):
        """很高重试次数仍然截断在 360s"""
        self.assertEqual(calculate_next_retry_delay(20), 360)

    def test_exact_boundary(self):
        """恰好不超限的边界：3 * 2^6 = 192 < 360"""
        self.assertEqual(calculate_next_retry_delay(7), 192)


if __name__ == '__main__':
    unittest.main()
