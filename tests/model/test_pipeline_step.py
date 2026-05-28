"""
PipelineStep 数据模型单元测试

测试 PipelineStep 的纯数据方法（不涉及数据库操作）：
- get_params_dict: 解析 params 字段
- get_result_data_dict: 解析 result_data 字段
- to_dict: 序列化为字典
- 常量值验证
"""
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock

# 保存原始模块引用，防止污染后续测试
_saved_model_database = sys.modules.get('model.database')

# Mock 数据库依赖（模块级 import 会触发）
sys.modules['model.database'] = MagicMock()

from model.ai_tool_pipeline_steps import (
    PipelineStep,
    PipelineStepStatus,
    PipelineStage,
    PipelineStepType,
)

# 恢复 model.database，防止污染后续测试
if _saved_model_database is not None:
    sys.modules['model.database'] = _saved_model_database
else:
    sys.modules.pop('model.database', None)


class TestPipelineStepConstants(unittest.TestCase):
    """测试 PipelineStep 常量值"""

    def test_status_values(self):
        """验证所有 PipelineStepStatus 常量值"""
        self.assertEqual(PipelineStepStatus.PENDING, 0)
        self.assertEqual(PipelineStepStatus.PROCESSING, 1)
        self.assertEqual(PipelineStepStatus.COMPLETED, 2)
        self.assertEqual(PipelineStepStatus.FAILED, -1)
        self.assertEqual(PipelineStepStatus.TIMEOUT, -2)

    def test_stage_values(self):
        """验证 PipelineStage 常量值"""
        self.assertEqual(PipelineStage.PARAM_PREPARE, 'param_prepare')
        self.assertEqual(PipelineStage.BEFORE_FINISH, 'before_finish')

    def test_type_values(self):
        """验证 PipelineStepType 常量值"""
        self.assertEqual(PipelineStepType.FACE_MASK, 'face_mask')
        self.assertEqual(PipelineStepType.IMPLEMENTATION_RETRY, 'implementation_retry')


class TestPipelineStepGetParamsDict(unittest.TestCase):
    """测试 PipelineStep.get_params_dict()"""

    def test_dict_input(self):
        """params 已是 dict 时直接返回"""
        step = PipelineStep(params={"key": "value", "num": 42})
        result = step.get_params_dict()
        self.assertEqual(result, {"key": "value", "num": 42})

    def test_json_string_input(self):
        """params 是 JSON 字符串时解析为 dict"""
        step = PipelineStep(params='{"name": "test", "count": 3}')
        result = step.get_params_dict()
        self.assertEqual(result, {"name": "test", "count": 3})

    def test_invalid_json_string(self):
        """params 是非法 JSON 字符串时返回空 dict"""
        step = PipelineStep(params='not valid json {{{')
        result = step.get_params_dict()
        self.assertEqual(result, {})

    def test_none_input(self):
        """params 为 None 时返回空 dict"""
        step = PipelineStep(params=None)
        result = step.get_params_dict()
        self.assertEqual(result, {})

    def test_number_input(self):
        """params 为非 dict/str 类型时返回空 dict"""
        step = PipelineStep(params=12345)
        result = step.get_params_dict()
        self.assertEqual(result, {})

    def test_nested_json(self):
        """params 包含嵌套结构"""
        step = PipelineStep(params='{"face": {"region": "forehead", "points": [1, 2, 3]}}')
        result = step.get_params_dict()
        self.assertEqual(result["face"]["region"], "forehead")
        self.assertEqual(result["face"]["points"], [1, 2, 3])


class TestPipelineStepGetResultDataDict(unittest.TestCase):
    """测试 PipelineStep.get_result_data_dict()"""

    def test_dict_input(self):
        """result_data 已是 dict 时直接返回"""
        step = PipelineStep(result_data={"url": "http://example.com/result.png"})
        result = step.get_result_data_dict()
        self.assertEqual(result, {"url": "http://example.com/result.png"})

    def test_json_string_input(self):
        """result_data 是 JSON 字符串时解析为 dict"""
        step = PipelineStep(result_data='{"url": "http://example.com/result.png"}')
        result = step.get_result_data_dict()
        self.assertEqual(result, {"url": "http://example.com/result.png"})

    def test_invalid_json_string(self):
        """result_data 是非法 JSON 字符串时返回空 dict"""
        step = PipelineStep(result_data='broken{json}')
        result = step.get_result_data_dict()
        self.assertEqual(result, {})

    def test_none_input(self):
        """result_data 为 None 时返回空 dict"""
        step = PipelineStep(result_data=None)
        result = step.get_result_data_dict()
        self.assertEqual(result, {})

    def test_number_input(self):
        """result_data 为非 dict/str 类型时返回空 dict"""
        step = PipelineStep(result_data=999)
        result = step.get_result_data_dict()
        self.assertEqual(result, {})


class TestPipelineStepToDict(unittest.TestCase):
    """测试 PipelineStep.to_dict()"""

    def test_basic_fields(self):
        """基本字段序列化"""
        step = PipelineStep(
            id=1,
            ai_tool_id=100,
            stage='param_prepare',
            step_type='face_mask',
            target='/path/to/video.mp4',
            step_order=0,
            status=PipelineStepStatus.PENDING,
            params={"key": "value"},
            result_data={"url": "http://example.com/result.png"},
            result_url='/path/to/result.mp4',
            error_message=None,
            async_task_id=50,
            retry_count=0,
            max_retries=5,
        )
        result = step.to_dict()

        self.assertEqual(result['id'], 1)
        self.assertEqual(result['ai_tool_id'], 100)
        self.assertEqual(result['stage'], 'param_prepare')
        self.assertEqual(result['step_type'], 'face_mask')
        self.assertEqual(result['target'], '/path/to/video.mp4')
        self.assertEqual(result['step_order'], 0)
        self.assertEqual(result['status'], PipelineStepStatus.PENDING)
        self.assertEqual(result['params'], {"key": "value"})
        self.assertEqual(result['result_data'], {"url": "http://example.com/result.png"})
        self.assertEqual(result['result_url'], '/path/to/result.mp4')
        self.assertEqual(result['error_message'], None)
        self.assertEqual(result['async_task_id'], 50)
        self.assertEqual(result['retry_count'], 0)
        self.assertEqual(result['max_retries'], 5)

    def test_datetime_fields_serialized(self):
        """datetime 字段序列化为 ISO 格式字符串"""
        now = datetime(2026, 5, 28, 14, 30, 0)
        step = PipelineStep(
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        result = step.to_dict()

        self.assertEqual(result['created_at'], "2026-05-28T14:30:00")
        self.assertEqual(result['updated_at'], "2026-05-28T14:30:00")
        self.assertEqual(result['completed_at'], "2026-05-28T14:30:00")

    def test_none_datetime_fields(self):
        """None 的 datetime 字段保持 None"""
        step = PipelineStep()
        result = step.to_dict()
        self.assertIsNone(result['created_at'])
        self.assertIsNone(result['updated_at'])
        self.assertIsNone(result['completed_at'])
        self.assertIsNone(result['next_retry_at'])

    def test_params_json_string_parsed(self):
        """params 为 JSON 字符串时，to_dict 返回解析后的 dict"""
        step = PipelineStep(params='{"face_region": "all", "threshold": 0.8}')
        result = step.to_dict()
        self.assertEqual(result['params'], {"face_region": "all", "threshold": 0.8})

    def test_result_data_included(self):
        """result_data 在输出中正确包含"""
        step = PipelineStep(result_data={"frames": [1, 2, 3]})
        result = step.to_dict()
        self.assertEqual(result['result_data'], {"frames": [1, 2, 3]})

    def test_error_message_field(self):
        """error_message 字段正确传递"""
        step = PipelineStep(error_message="Face detection failed")
        result = step.to_dict()
        self.assertEqual(result['error_message'], "Face detection failed")

    def test_all_default_values(self):
        """默认构造函数，验证所有默认值"""
        step = PipelineStep()
        self.assertIsNone(step.id)
        self.assertIsNone(step.ai_tool_id)
        self.assertIsNone(step.stage)
        self.assertIsNone(step.step_type)
        self.assertIsNone(step.target)
        self.assertEqual(step.step_order, 0)
        self.assertEqual(step.status, PipelineStepStatus.PENDING)
        self.assertIsNone(step.params)
        self.assertIsNone(step.result_data)
        self.assertIsNone(step.result_url)
        self.assertIsNone(step.error_message)
        self.assertIsNone(step.async_task_id)
        self.assertEqual(step.retry_count, 0)
        self.assertIsNone(step.next_retry_at)
        self.assertEqual(step.max_retries, 5)
        self.assertIsNone(step.created_at)
        self.assertIsNone(step.updated_at)
        self.assertIsNone(step.completed_at)


if __name__ == '__main__':
    unittest.main()
