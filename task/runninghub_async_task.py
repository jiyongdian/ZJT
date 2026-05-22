"""
RunningHub 异步任务处理
在 scheduler 进程中定时轮询 RunningHub 任务状态并更新数据库

使用通用 async_tasks 表，通过 implementation = AsyncTaskImplementationId.RUNNINGHUB_AUDIO 区分任务。
"""
import logging
import os
from typing import Any

from model import AsyncTasksModel, AsyncTaskStatus
from config.unified_config import AsyncTaskImplementationId
from task.async_drivers.runninghub_audio_driver import RunningHubAudioDriver

logger = logging.getLogger(__name__)


def _setup_cdn_mapping(task: Any, local_path: str, original_url: str, character_id: int):
    """
    创建或替换 CDN mapping 记录，触发异步上传
    复用 ensure_entity_image_mapping，传入 label="voice"

    Args:
        task: AsyncTask 对象
        local_path: 本地相对路径（如 "upload/character/voice/rh_voice_xxx.wav"）
        original_url: 原始远程 URL
        character_id: 角色 ID
    """
    from utils.media_mapping_util import ensure_entity_image_mapping
    from model.media_file_mapping import MediaFileEntity

    ensure_entity_image_mapping(
        user_id=task.user_id,
        image_url=f"/{local_path}",
        entity_type=MediaFileEntity.CHARACTER,
        entity_id=character_id,
        label="voice"
    )


def _handle_audio_task_success(task: Any, result_url: str):
    """
    处理音频任务成功的情况：
    1. 下载音频到本地 upload/character/voice/
    2. 如果开启图床，创建 CDN mapping 并触发上传
    3. 更新角色的 default_voice 为本地路径

    Args:
        task: AsyncTask 对象
        result_url: RunningHub 远程音频 URL
    """
    from datetime import datetime

    params = task.get_params_dict()
    character_id = params.get('character_id')
    character_name = params.get('character_name')

    # Step 1: 下载音频到本地
    voice_url = result_url  # 默认使用远程 URL（下载失败时回退）
    local_path = None

    try:
        from utils.audio_utils import download_and_save_character_voice
        local_path = download_and_save_character_voice(
            remote_url=result_url,
            filename_prefix="rh_voice"
        )
        if local_path:
            voice_url = f"/{local_path}"
            logger.info(f"Audio saved locally, voice_url: {voice_url}")
        else:
            logger.warning(f"Failed to download audio, using remote URL: {result_url}")
    except Exception as e:
        logger.error(f"Download audio failed: {e}", exc_info=True)

    # Step 2: 如果开启 CDN 且有 character_id，创建 mapping 并触发上传
    if local_path and character_id:
        try:
            from config.config_util import get_config
            enable_cdn = get_config().get("server", {}).get("auto_upload_to_cdn", False)
            if enable_cdn:
                _setup_cdn_mapping(task, local_path, result_url, character_id)
        except Exception as e:
            logger.error(f"CDN mapping setup failed: {e}", exc_info=True)

    # Step 3: 更新角色的 default_voice
    # 优先通过 character_id 更新数据库
    if character_id:
        try:
            from model.character import CharacterModel
            CharacterModel.update(character_id, default_voice=voice_url)
            logger.info(f"Updated character {character_id} default_voice: {voice_url}")
            return
        except Exception as e:
            logger.error(f"Failed to update character default_voice by id: {e}")

    # 通过 character_name 更新角色 JSON 文件
    if character_name and task.user_id:
        try:
            from script_writer_core.file_manager import FileManager
            file_manager = FileManager()
            uid = str(task.user_id)
            world_id = params.get('world_id', uid)
            character_data = file_manager.get_character_json(character_name, uid, world_id)
            if character_data:
                character_data['default_voice'] = voice_url
                character_data['updated_at'] = datetime.now().isoformat()
                from script_writer_core.mcp_tool import _sanitize_filename
                filename = f"character_{_sanitize_filename(character_name)}.json"
                file_manager.save_json_content(uid, world_id, "characters", filename, character_data)
                logger.info(f"Updated character '{character_name}' default_voice via FileManager: {voice_url}")
            else:
                logger.warning(f"Character '{character_name}' not found in FileManager")
        except Exception as e:
            logger.error(f"Failed to update character default_voice by name: {e}")
    else:
        logger.warning(f"No character_id or character_name in task params, skipping update")

    return local_path


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
                    AsyncTasksModel.increment_try_count(task.id)
                    task.try_count += 1

                    # 检查是否超过最大尝试次数
                    if task.try_count > task.max_attempts:
                        logger.error(f"RunningHub 异步任务超时: {task.id}, 尝试次数: {task.try_count}/{task.max_attempts}")
                        AsyncTasksModel.update_status(
                            record_id=task.id,
                            status=AsyncTaskStatus.TIMEOUT,
                            error_message=f"超过最大尝试次数 {task.max_attempts}"
                        )
                        continue

                    # 更新为处理中状态（仅在第一次尝试时）
                    if task.try_count == 1:
                        AsyncTasksModel.update_status(
                            record_id=task.id,
                            status=AsyncTaskStatus.PROCESSING
                        )

                    # 查询 RunningHub 任务状态
                    status_result = loop.run_until_complete(driver.check_status(task.external_task_id))

                    if status_result.get('status') == 'SUCCESS':
                        result_url = status_result.get('result_url')

                        # 处理音频：下载、CDN 上传、更新角色
                        local_path = _handle_audio_task_success(task, result_url)

                        # 更新 async_tasks 记录的 result_url 为本地路径
                        async_result_url = f"/{local_path}" if local_path else result_url
                        AsyncTasksModel.update_status(
                            record_id=task.id,
                            status=AsyncTaskStatus.COMPLETED,
                            result_url=async_result_url
                        )
                        logger.info(f"RunningHub 异步任务完成: {task.id}, result: {async_result_url}")

                    elif status_result.get('status') == 'FAILED':
                        error_message = status_result.get('error', '任务失败')
                        AsyncTasksModel.update_status(
                            record_id=task.id,
                            status=AsyncTaskStatus.FAILED,
                            error_message=error_message
                        )
                        logger.error(f"RunningHub 异步任务失败: {task.id}, error: {error_message}")

                    # RUNNING 状态不做处理，等待下次轮询

                except Exception as e:
                    logger.error(f"处理 RunningHub 异步任务异常: {task.id}, error: {str(e)}")
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"处理 RunningHub 异步任务失败: {e}")
