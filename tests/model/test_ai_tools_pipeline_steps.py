"""
AIToolsModel.create_with_pipeline_steps 单元测试

验证 Seedance 前置处理步骤在实际 ai_tools 创建入口中的生成行为。
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from model.ai_tools import AIToolsModel
from model.ai_tool_pipeline_steps import PipelineStepType, PipelineStage


class _FakeTransaction:
    def __init__(self):
        self.conn = MagicMock(name="conn")

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class TestCreateWithPipelineSteps(unittest.TestCase):
    """测试创建 ai_tool 时同步创建前置处理步骤"""

    def _call_create(self, **overrides):
        params = {
            'prompt': 'test prompt',
            'user_id': 1,
            'type': 100,
            'image_path': None,
            'reference_images': None,
            'video_path': None,
        }
        params.update(overrides)
        return AIToolsModel.create_with_pipeline_steps(**params)

    @patch('config.config_util.get_dynamic_config_value')
    @patch('config.constant.Edition.is_community', return_value=False)
    @patch('model.ai_tool_pipeline_steps.PipelineStepModel.create_in_transaction')
    @patch('model.database.execute_insert_in_transaction', return_value=123)
    @patch('model.database.transaction', return_value=_FakeTransaction())
    def test_creates_video_and_image_face_mask_steps(
        self,
        mock_transaction,
        mock_insert,
        mock_create_step,
        mock_is_community,
        mock_config,
    ):
        """视频、首尾帧、参考图都会创建对应前置处理步骤"""
        mock_config.return_value = True

        result = self._call_create(
            image_path='start.png,end.png',
            reference_images=json.dumps(['ref.png']),
            video_path='clip.mp4',
        )

        self.assertEqual(result, 123)
        self.assertEqual(mock_create_step.call_count, 4)

        step_types = [call.kwargs['step_type'] for call in mock_create_step.call_args_list]
        self.assertEqual(step_types, [
            PipelineStepType.FACE_MASK,
            PipelineStepType.IMAGE_FACE_MASK,
            PipelineStepType.IMAGE_FACE_MASK,
            PipelineStepType.IMAGE_FACE_MASK,
        ])
        self.assertTrue(all(call.kwargs['stage'] == PipelineStage.PARAM_PREPARE for call in mock_create_step.call_args_list))

        params = [call.kwargs['params'] for call in mock_create_step.call_args_list]
        self.assertEqual(params[1]['field'], 'image_path')
        self.assertEqual(params[1]['index'], 0)
        self.assertEqual(params[2]['field'], 'image_path')
        self.assertEqual(params[2]['index'], 1)
        self.assertEqual(params[3]['field'], 'reference_images')
        self.assertEqual(params[3]['index'], 0)

    @patch('config.config_util.get_dynamic_config_value')
    @patch('config.constant.Edition.is_community', return_value=False)
    @patch('model.ai_tool_pipeline_steps.PipelineStepModel.create_in_transaction')
    @patch('model.database.execute_insert_in_transaction', return_value=123)
    @patch('model.database.transaction', return_value=_FakeTransaction())
    def test_image_face_mask_switch_off_skips_image_steps(
        self,
        mock_transaction,
        mock_insert,
        mock_create_step,
        mock_is_community,
        mock_config,
    ):
        """图片前置处理开关关闭时不创建 image_face_mask 步骤"""
        mock_config.return_value = False

        result = self._call_create(
            image_path='start.png,end.png',
            reference_images=json.dumps(['ref.png']),
            video_path=None,
        )

        self.assertEqual(result, 123)
        mock_create_step.assert_not_called()


if __name__ == '__main__':
    unittest.main()
