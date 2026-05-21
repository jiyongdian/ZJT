"""
RunningHub 音频生成驱动
使用 RunningHub OpenAPI v2 异步生成音频
"""
import logging
import traceback
from typing import Dict, Any, Optional

from .base_async_driver import BaseAsyncDriver
from api.clients.runninghub_client import RunningHubClient
from config.constant import RunningHubAudioConfig

logger = logging.getLogger(__name__)


class RunningHubAudioDriver(BaseAsyncDriver):
    """
    RunningHub 音频生成驱动

    使用 RunningHub AI App 异步生成音频。
    对应的 App ID 和节点 ID 在 RunningHubAudioConfig 中配置。
    """

    def __init__(self):
        super().__init__("runninghub_audio")
        self._client = RunningHubClient()

    async def submit_task(
        self,
        style_prompt: str,
        text: str,
    ) -> Dict[str, Any]:
        """
        提交音频生成任务到 RunningHub

        Args:
            style_prompt: 音色风格提示词
            text: 要朗读的文本内容

        Returns:
            Dict[str, Any]: 结果字典
                成功: {"success": True, "project_id": "taskId"}
                失败: {"success": False, "error": "...", "error_type": "USER"|"SYSTEM", "retry": bool}
        """
        try:
            node_info_list = [
                {
                    'nodeId': RunningHubAudioConfig.STYLE_NODE_ID,
                    'fieldName': 'prompt',
                    'fieldValue': style_prompt,
                    'description': 'prompt'
                },
                {
                    'nodeId': RunningHubAudioConfig.TEXT_NODE_ID,
                    'fieldName': 'prompt',
                    'fieldValue': text,
                    'description': 'prompt'
                }
            ]

            submit_response = await self._client.run_ai_app_v2(
                app_id=RunningHubAudioConfig.APP_ID,
                node_info_list=node_info_list,
                instance_type='default',
                use_personal_queue='false'
            )

            runninghub_task_id = submit_response.get('taskId')
            if not runninghub_task_id:
                error_message = submit_response.get('errorMessage') or 'RunningHub 未返回任务 ID'
                return {
                    'success': False,
                    'error': error_message,
                    'error_type': 'SYSTEM',
                    'error_detail': f"RunningHub response: {submit_response}",
                    'retry': False
                }

            return {
                'success': True,
                'project_id': runninghub_task_id
            }

        except ConnectionError as e:
            logger.error(f"RunningHub audio submit connection error: {e}")
            return {
                'success': False,
                'error': '网络连接异常，请稍后重试',
                'error_type': 'USER',
                'retry': True
            }
        except TimeoutError as e:
            logger.error(f"RunningHub audio submit timeout: {e}")
            return {
                'success': False,
                'error': '请求超时，请稍后重试',
                'error_type': 'USER',
                'retry': True
            }
        except Exception as e:
            logger.error(f"RunningHub audio submit error: {e}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': f'提交音频生成任务失败: {str(e)}',
                'error_type': 'SYSTEM',
                'error_detail': traceback.format_exc(),
                'retry': False
            }

    async def check_status(self, project_id: str) -> Dict[str, Any]:
        """
        查询 RunningHub 音频生成任务状态

        Args:
            project_id: RunningHub 任务 ID

        Returns:
            Dict[str, Any]: 结果字典
                RUNNING: {"status": "RUNNING"}
                SUCCESS: {"status": "SUCCESS", "result_url": "..."}
                FAILED:  {"status": "FAILED", "error": "...", "error_type": "USER"|"SYSTEM"}
        """
        try:
            query_response = await self._client.query_v2_task(project_id)
            remote_status = query_response.get('status')

            if remote_status == 'SUCCESS':
                result_url = self._extract_result_url(query_response)
                if result_url:
                    return {
                        'status': 'SUCCESS',
                        'result_url': result_url
                    }
                else:
                    return {
                        'status': 'FAILED',
                        'error': '任务成功但未返回结果 URL',
                        'error_type': 'SYSTEM',
                        'error_detail': f"Response: {query_response}"
                    }

            if remote_status in RunningHubAudioConfig.FINAL_STATUSES:
                error_message = (
                    query_response.get('errorMessage')
                    or str(query_response.get('failedReason') or '音频生成失败')
                )
                return {
                    'status': 'FAILED',
                    'error': error_message,
                    'error_type': 'USER'
                }

            return {
                'status': 'RUNNING'
            }

        except ConnectionError as e:
            logger.error(f"RunningHub audio check connection error: {e}")
            return {
                'status': 'FAILED',
                'error': '网络连接异常，请稍后重试',
                'error_type': 'USER',
                'retry': True
            }
        except TimeoutError as e:
            logger.error(f"RunningHub audio check timeout: {e}")
            return {
                'status': 'FAILED',
                'error': '请求超时，请稍后重试',
                'error_type': 'USER',
                'retry': True
            }
        except Exception as e:
            logger.error(f"RunningHub audio check error: {e}\n{traceback.format_exc()}")
            return {
                'status': 'FAILED',
                'error': f'查询音频状态失败: {str(e)}',
                'error_type': 'SYSTEM',
                'error_detail': traceback.format_exc()
            }

    @staticmethod
    def _extract_result_url(response_data: Dict[str, Any]) -> Optional[str]:
        """从 RunningHub v2 响应中提取结果 URL"""
        for item in response_data.get('results') or []:
            result_url = item.get('url')
            if result_url:
                return result_url
        return None
