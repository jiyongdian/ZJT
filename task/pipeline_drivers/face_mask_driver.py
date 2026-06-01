"""
人脸遮盖 Pipeline 驱动
委托现有 RunningHubFaceMaskDriver 处理，通过 async_tasks 表异步执行。
"""
import logging
from typing import Dict, Any

from .base_pipeline_driver import BasePipelineDriver
from model import PipelineStep, AITool

logger = logging.getLogger(__name__)


class FaceMaskPipelineDriver(BasePipelineDriver):
    """
    人脸遮盖 Pipeline 驱动

    流程：
    1. 从 step.params 中获取 video_path
    2. 调用 RunningHubFaceMaskDriver.submit_task() 提交到 RunningHub
    3. 创建 async_task 记录并关联到 pipeline step
    4. 后续由 process_runninghub_async_tasks 轮询 async_task 状态
    5. check_async_status 查询 async_task 完成后，将 result_url 写入 step.result_data
    """

    def __init__(self):
        super().__init__("face_mask")

    async def execute(self, step: PipelineStep, ai_tool: AITool) -> Dict[str, Any]:
        """
        提交人脸遮盖任务（使用统一槽位管理）

        Args:
            step: PipelineStep 对象，params 中应包含 video_path
            ai_tool: AITool 对象

        Returns:
            Dict 包含 success, async_task_id 或 error
        """
        try:
            params = step.get_params_dict()
            video_path = params.get('video_path')

            if not video_path:
                return {
                    'success': False,
                    'error': '缺少 video_path 参数'
                }

            # 使用基类的统一槽位管理方法
            from task.async_drivers.runninghub_face_mask_driver import RunningHubFaceMaskDriver
            driver = RunningHubFaceMaskDriver()

            result = await driver.submit_with_slot_management(
                user_id=ai_tool.user_id,
                params={'video_path': video_path, 'pipeline_step_id': step.id},
                submit_fn=lambda: driver.submit_task(video_path=video_path)
            )

            if result.get('success'):
                self.logger.info(
                    f"Face mask task submitted: async_task_id={result.get('async_task_id')}, "
                    f"project_id={result.get('project_id')}, step_id={step.id}"
                )
                return {
                    'success': True,
                    'async_task_id': result.get('async_task_id')
                }

            # 保持原有的错误类型传递（SLOT_FULL 等）
            return result

        except Exception as e:
            self.logger.error(f"Face mask execute error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'提交人脸遮盖任务异常: {str(e)}'
            }
