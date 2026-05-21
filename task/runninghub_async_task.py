"""
RunningHub 异步任务处理
在 scheduler 进程中定时轮询 RunningHub 任务状态并更新数据库

使用通用 async_tasks 表，通过 implementation = AsyncTaskImplementationId.RUNNINGHUB_AUDIO 区分任务。
"""
import logging
from typing import Any

from model import AsyncTasksModel, AsyncTaskStatus
from config.unified_config import AsyncTaskImplementationId
from task.async_drivers.runninghub_audio_driver import RunningHubAudioDriver

logger = logging.getLogger(__name__)


def _handle_audio_task_success(task: Any, result_url: str):
    """
    处理音频任务成功的情况：更新角色的 default_voice

    Args:
        task: AsyncTask 对象
        result_url: 生成的音频 URL
    """
    params = task.get_params_dict()
    character_id = params.get('character_id')

    if not character_id:
        return

    try:
        from model.character import CharacterModel
        CharacterModel.update(character_id, default_voice=result_url)
        logger.info(f"Updated character {character_id} default_voice: {result_url}")
    except Exception as e:
        logger.error(f"Failed to update character default_voice: {e}")


def process_runninghub_async_tasks(app=None):
    """
    处理 RunningHub 异步任务（在 scheduler 进程中定时执行）

    流程：
    1. 从 async_tasks 表获取 implementation=RUNNINGHUB_AUDIO 且状态为 QUEUED/PROCESSING 的任务
    2. 调用 RunningHubAudioDriver.check_status() 查询远程状态
    3. 根据结果更新数据库
    """
    import asyncio

    try:
        pending_tasks = AsyncTasksModel.get_pending_tasks(
            implementation=AsyncTaskImplementationId.RUNNINGHUB_AUDIO,
            limit=50
        )

        if not pending_tasks:
            return

        logger.info(f"开始处理 {len(pending_tasks)} 个 RunningHub 异步任务")

        driver = RunningHubAudioDriver()

        # 在循环外创建事件循环，避免每次迭代创建/销毁
        loop = asyncio.new_event_loop()
        try:
            for task in pending_tasks:
                try:
                    # 增加尝试次数
                    AsyncTasksModel.increment_try_count(task.task_key)
                    task.try_count += 1

                    # 检查是否超过最大尝试次数
                    if task.try_count > task.max_attempts:
                        logger.error(f"RunningHub 异步任务超时: {task.task_key}, 尝试次数: {task.try_count}/{task.max_attempts}")
                        AsyncTasksModel.update_status(
                            task_key=task.task_key,
                            status=AsyncTaskStatus.TIMEOUT,
                            error_message=f"超过最大尝试次数 {task.max_attempts}"
                        )
                        continue

                    # 更新为处理中状态（仅在第一次尝试时）
                    if task.try_count == 1:
                        AsyncTasksModel.update_status(
                            task_key=task.task_key,
                            status=AsyncTaskStatus.PROCESSING
                        )

                    # 查询 RunningHub 任务状态
                    status_result = loop.run_until_complete(driver.check_status(task.external_task_id))

                    if status_result.get('status') == 'SUCCESS':
                        result_url = status_result.get('result_url')
                        AsyncTasksModel.update_status(
                            task_key=task.task_key,
                            status=AsyncTaskStatus.COMPLETED,
                            result_url=result_url
                        )
                        _handle_audio_task_success(task, result_url)
                        logger.info(f"RunningHub 异步任务完成: {task.task_key}, result: {result_url}")

                    elif status_result.get('status') == 'FAILED':
                        error_message = status_result.get('error', '任务失败')
                        AsyncTasksModel.update_status(
                            task_key=task.task_key,
                            status=AsyncTaskStatus.FAILED,
                            error_message=error_message
                        )
                        logger.error(f"RunningHub 异步任务失败: {task.task_key}, error: {error_message}")

                    # RUNNING 状态不做处理，等待下次轮询

                except Exception as e:
                    logger.error(f"处理 RunningHub 异步任务异常: {task.task_key}, error: {str(e)}")
        finally:
            loop.close()

        # 清理旧任务（7天前）
        try:
            AsyncTasksModel.cleanup_old_tasks(days=7, implementation=AsyncTaskImplementationId.RUNNINGHUB_AUDIO)
        except Exception as e:
            logger.error(f"清理旧 RunningHub 异步任务失败: {e}")

    except Exception as e:
        logger.error(f"处理 RunningHub 异步任务失败: {e}")
