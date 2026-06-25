"""
图片人脸遮盖 Pipeline 驱动
委托 RunningHubImageFaceMaskDriver 处理，通过 async_tasks 表异步执行。
"""
from typing import Dict, Any

from .base_pipeline_driver import BasePipelineDriver
from model import PipelineStep, AITool


class ImageFaceMaskPipelineDriver(BasePipelineDriver):
    """图片人脸遮盖 Pipeline 驱动"""

    def __init__(self):
        super().__init__("image_face_mask")

    async def execute(self, step: PipelineStep, ai_tool: AITool) -> Dict[str, Any]:
        """
        提交图片人脸遮盖任务（使用统一槽位管理）。
        """
        try:
            params = step.get_params_dict()
            image_path = params.get('image_path')

            if not image_path:
                return {
                    'success': False,
                    'error': '缺少 image_path 参数'
                }

            from task.async_drivers.runninghub_image_face_mask_driver import RunningHubImageFaceMaskDriver
            driver = RunningHubImageFaceMaskDriver()

            result = await driver.submit_with_slot_management(
                user_id=ai_tool.user_id,
                params={
                    **params,
                    'image_path': image_path,
                    'pipeline_step_id': step.id
                },
                submit_fn=lambda: driver.submit_task(image_path=image_path)
            )

            if result.get('success'):
                self.logger.info(
                    f"Image face mask task submitted: async_task_id={result.get('async_task_id')}, "
                    f"project_id={result.get('project_id')}, step_id={step.id}"
                )
                return {
                    'success': True,
                    'async_task_id': result.get('async_task_id')
                }

            return result

        except Exception as e:
            self.logger.error(f"Image face mask execute error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'提交图片人脸遮盖任务异常: {str(e)}'
            }
