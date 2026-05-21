"""
Audio generation task processing
"""
import logging
from datetime import datetime, timedelta
import uuid
from typing import Optional, Dict, Any
from model import TasksModel, AIAudioModel
from config.constant import (
    TASK_TYPE_GENERATE_AUDIO,
    AI_AUDIO_STATUS_PENDING,
    AI_AUDIO_STATUS_PROCESSING,
    AI_AUDIO_STATUS_COMPLETED,
    AI_AUDIO_STATUS_FAILED,
    TASK_STATUS_QUEUED,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    RunningHubAudioConfig
)
from utils.index_tts_util import generate_audio, validate_emotion_vector
import os
from config.config_util import get_dynamic_config_value

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _get_max_retry_count():
    """动态获取最大重试次数"""
    return get_dynamic_config_value("task_queue", "max_retry_count", default=30)

def _get_task_expire_days():
    """动态获取任务过期天数"""
    return get_dynamic_config_value("task_queue", "task_expire_days", default=7)

def _is_expire_check_enabled():
    """动态获取是否启用过期检查"""
    return get_dynamic_config_value("task_queue", "enable_expire_check", default=True)

# Get upload directory path
UPLOAD_DIR = "/home/appuser/comfyui_upload/tts/result_audio/"


async def _submit_new_task(ai_audio):
    """
    Submit a new audio generation task (status == AI_AUDIO_STATUS_PENDING)
    
    Args:
        ai_audio: AIAudio object
    
    Returns:
        bool: True if successful, False otherwise
    """
    task_id = ai_audio.id
    
    try:
        AIAudioModel.update(task_id, status=AI_AUDIO_STATUS_PROCESSING, message="任务处理中")
        TasksModel.update_by_task_id(task_id, status=TASK_STATUS_PROCESSING)
        # Prepare parameters for generate_audio
        text = ai_audio.text
        
        # Get reference audio path
        spk_audio_path = ai_audio.ref_path
        if not spk_audio_path:
            logger.error(f"Task {task_id}: No reference audio path provided")
            AIAudioModel.update(task_id, status=AI_AUDIO_STATUS_FAILED, message="缺少参考音频")
            TasksModel.update_by_task_id(task_id, status=TASK_STATUS_FAILED)
            return False
        
        
        # Get emotion control parameters
        emo_control_method = ai_audio.emo_control_method or 0
        emo_ref_path = None
        emo_weight = ai_audio.emo_weight if ai_audio.emo_weight is not None else 1.0
        emo_vec = None
        emo_text = ai_audio.emo_text
        
        # Handle emotion reference audio path
        if emo_control_method == 1 and ai_audio.emo_ref_path:
            emo_ref_path = ai_audio.emo_ref_path
        
        # Handle emotion vector
        if emo_control_method == 2 and ai_audio.emo_vec:
            try:
                # Parse emotion vector from comma-separated string
                if isinstance(ai_audio.emo_vec, str):
                    emo_vec = [float(x.strip()) for x in ai_audio.emo_vec.split(',')]
                else:
                    emo_vec = ai_audio.emo_vec
                
                # Validate emotion vector
                is_valid, error_msg = validate_emotion_vector(emo_vec)
                if not is_valid:
                    logger.error(f"Task {task_id}: Invalid emotion vector - {error_msg}")
                    AIAudioModel.update(task_id, status=AI_AUDIO_STATUS_FAILED, message=error_msg)
                    TasksModel.update_by_task_id(task_id, status=TASK_STATUS_FAILED)
                    return False
            except Exception as e:
                logger.error(f"Task {task_id}: Failed to parse emotion vector - {str(e)}")
                AIAudioModel.update(task_id, status=AI_AUDIO_STATUS_FAILED, message=f"情感向量解析失败: {str(e)}")
                TasksModel.update_by_task_id(task_id, status=TASK_STATUS_FAILED)
                return False
        
        # Prepare target path for generated audio
        # os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        audio_filename = f"audio_{timestamp}_{unique_id}.wav"
        result_path = os.path.join(UPLOAD_DIR, audio_filename)
        
        logger.info(f"Task {task_id}: Calling generate_audio with text='{text[:50]}...', emo_control_method={emo_control_method}, result_path={result_path}")
        
        # Call generate_audio utility
        success, audio_path_or_error = await generate_audio(
            text=text,
            spk_audio_path=spk_audio_path,
            emo_control_method=emo_control_method,
            emo_ref_path=emo_ref_path,
            emo_weight=emo_weight,
            emo_vec=emo_vec,
            emo_text=emo_text,
            result_path=result_path
        )
        
        if not success:
            logger.error(f"Task {task_id}: Audio generation failed - {audio_path_or_error}")
            AIAudioModel.update(task_id, status=AI_AUDIO_STATUS_FAILED, message=audio_path_or_error)
            TasksModel.update_by_task_id(task_id, status=TASK_STATUS_FAILED)
            return False
        
        audio_file_path = audio_path_or_error or result_path
        
        logger.info(f"Task {task_id}: Audio saved to {audio_file_path}")
        upload_url = get_dynamic_config_value("tts", "upload_url")
        result_url = f"{upload_url}{audio_filename}"
        # Update database with result
        AIAudioModel.update(task_id, status=AI_AUDIO_STATUS_COMPLETED, result_url=result_url, message="音频生成成功")
        TasksModel.update_by_task_id(task_id, status=TASK_STATUS_COMPLETED)
        
        logger.info(f"Task {task_id}: Audio generation completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to submit audio generation task - {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def calculate_next_retry_delay(try_count):
    """
    Calculate next retry delay time
    
    Args:
        try_count: Number of attempts made
    
    Returns:
        Delay in seconds, maximum 360 seconds
    """
    base_delay = 3
    max_delay = 360
    delay_seconds = base_delay * (2 ** (try_count - 1))
    return min(delay_seconds, max_delay)


def _check_task_expiration(task):
    """
    检查任务是否已过期
    
    Args:
        task: Task对象
    
    Returns:
        bool: True表示任务已过期
    """
    if not _is_expire_check_enabled():
        return False
    
    if not task.created_at:
        return False
    
    task_age = datetime.now() - task.created_at
    if task_age.days >= _get_task_expire_days():
        logger.warning(f"Task {task.task_id} expired (created {task_age.days} days ago)")
        return True
    
    return False


def _check_max_retry_exceeded(task):
    """
    检查任务是否超过最大重试次数
    
    Args:
        task: Task对象
    
    Returns:
        bool: True表示超过最大重试次数
    """
    if task.try_count and task.try_count >= _get_max_retry_count():
        logger.warning(f"Task {task.task_id} exceeded max retry count ({task.try_count}/{_get_max_retry_count()})")
        return True
    
    return False


async def process_generate_audio(task):
    """Process audio generation task logic"""
    try:
        logger.info(f"Processing audio generation task: {task.task_id}")
        ai_audio = AIAudioModel.get_by_id(task.task_id)
        logger.info(f"AI audio {task.task_id} is {ai_audio}")
        
        if not ai_audio:
            logger.error(f"Failed to get AI audio record by ID {task.task_id}")
            return False
        
        status = ai_audio.status
        
        if status == AI_AUDIO_STATUS_PENDING:
            return await _submit_new_task(ai_audio)
        else:
            logger.warning(f"Unexpected status {status} for task {task.task_id}")
            return False
        
    except Exception as e:
        logger.error(f"Failed to process video generation task: {str(e)}")
        return False


async def process_task_with_retry(task_type, process_func):
    """
    Generic task processing function with retry logic
    
    Args:
        task_type: Task type
        process_func: Specific task processing function
    
    Returns:
        Tuple of (has_task, process_result)
    """
    try:
        # Query tasks by type with status 0 (队列中) or 1 (处理中)
        tasks = TasksModel.list_by_type_and_status(task_type, status_list=[0])
        
        if not tasks:
            logger.info(f"No pending {task_type} tasks with status 0")
            return False, False
        
        logger.info(f"Found {len(tasks)} tasks to process for type: {task_type}")
        
        # Loop through all tasks
        processed_count = 0
        success_count = 0
        expired_count = 0
        
        for task in tasks:
            try:
                logger.info(f"Start processing task: {task.task_id}, status: {task.status}, try_count: {task.try_count}")
                
                # 检查任务是否过期
                if _check_task_expiration(task):
                    TasksModel.update_by_task_id(task.task_id, status=TASK_STATUS_FAILED)
                    AIAudioModel.update(task.task_id, status=AI_AUDIO_STATUS_FAILED, message="任务已过期")
                    expired_count += 1
                    logger.info(f"Task {task.task_id} marked as expired")
                    continue
                
                # 检查是否超过最大重试次数
                if _check_max_retry_exceeded(task):
                    TasksModel.update_by_task_id(task.task_id, status=TASK_STATUS_FAILED)
                    AIAudioModel.update(task.task_id, status=AI_AUDIO_STATUS_FAILED, message=f"超过最大重试次数({_get_max_retry_count()})")
                    expired_count += 1
                    logger.info(f"Task {task.task_id} marked as failed due to max retry exceeded")
                    continue
                
                # Update status to 1 (处理中) if it's 0 (队列中)
                if task.status == TASK_STATUS_QUEUED:
                    TasksModel.update_by_task_id(task.task_id, status=TASK_STATUS_PROCESSING)
                    logger.info(f"Updated task {task.task_id} status to TASK_STATUS_PROCESSING (处理中)")
                
                # Call the specific processing function
                success = await process_func(task)
                processed_count += 1
                
                if success:
                    logger.info(f"Task completed successfully: {task.task_id}")
                    success_count += 1
                else:
                    # Failed - increment retry count and update status to -1 (处理失败)
                    new_try_count = (task.try_count or 0) + 1
                    delay_seconds = calculate_next_retry_delay(new_try_count)
                    next_trigger = datetime.now() + timedelta(seconds=delay_seconds)
                    
                    TasksModel.update_by_task_id(
                        task.task_id,
                        try_count=new_try_count,
                        next_trigger=next_trigger
                    )
                    logger.info(f"Task failed: {task.task_id}, retry count: {new_try_count}, status: -1 (处理失败), next trigger: {next_trigger}")
                    
            except Exception as e:
                logger.error(f"Error processing task {task.task_id}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                
        logger.info(f"Summary: processed={processed_count}, succeeded={success_count}, expired={expired_count}")
        return processed_count > 0, success_count > 0
            
    except Exception as e:
        logger.error(f"Task processing error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False, False


async def generate_audio_task(app=None):
    """Audio generation task entry point"""
    await process_task_with_retry(TASK_TYPE_GENERATE_AUDIO, process_generate_audio)


def build_character_audio_text(character_data: Dict[str, Any], custom_text: Optional[str]) -> str:
    """
    构建角色音频文本

    Args:
        character_data: 角色数据字典
        custom_text: 自定义文本（可选）

    Returns:
        str: 音频文本
    """
    if custom_text and custom_text.strip():
        return custom_text.strip()
    character_name = character_data.get('name') or '我'
    identity = character_data.get('identity') or '故事中的角色'
    return f"大家好，我是{character_name}，是{identity}。很高兴在这个故事里与你相遇。"


async def build_character_audio_style_prompt(
    character_data: Dict[str, Any],
    custom_prompt: Optional[str],
    model: Optional[str] = None,
    vendor_id: Optional[int] = None
) -> str:
    """
    构建角色音色风格提示词。
    如果用户提供了自定义提示词，直接返回；
    否则调用 LLM 根据角色信息自动生成专业的音色描述。

    Args:
        character_data: 角色数据字典
        custom_prompt: 自定义提示词（可选）
        model: LLM 模型名称（可选）
        vendor_id: 供应商 ID（可选）

    Returns:
        str: 音色风格提示词
    """
    # 1. 用户自定义提示词优先
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()

    # 2. 角色数据为空时返回默认提示词
    if not character_data:
        return RunningHubAudioConfig.AUDIO_STYLE_DEFAULT_PROMPT

    # 3. 构建角色信息文本
    field_mapping = {
        'name': '角色名',
        'age': '年龄',
        'identity': '身份',
        'personality': '性格',
        'behavior': '行为习惯',
        'other_info': '补充设定',
    }
    character_lines = []
    for key, label in field_mapping.items():
        value = character_data.get(key)
        if value and str(value).strip():
            character_lines.append(f"{label}：{str(value).strip()}")

    if not character_lines:
        return RunningHubAudioConfig.AUDIO_STYLE_DEFAULT_PROMPT

    # 4. 前端未传模型信息时 fallback
    if not model:
        return RunningHubAudioConfig.AUDIO_STYLE_DEFAULT_PROMPT

    # 5. 构造 LLM 提示词
    system_prompt = (
        "你是一位专业的声音设计师，擅长根据角色设定生成精准的音色描述。\n\n"
        "你的任务是根据用户提供的角色信息，生成一段简洁的音色描述提示词，用于 AI 音频生成系统。\n\n"
        "要求：\n"
        '1. 描述必须聚焦于"声音特征"：音色、音调、语速、语气、年龄感、性别特征\n'
        "2. 长度控制在一两句话以内（20-50字）\n"
        "3. 只输出音色描述本身，不要输出任何解释、前缀或多余内容\n"
        "4. 如果角色信息包含明确的声音相关描述（如性格急躁、温柔等），据此推断声音特征\n"
        "5. 如果角色信息不足以推断声音特征，根据角色的年龄、身份、性别做合理推断\n\n"
        "参考示例：\n"
        '- "一位30岁左右的成熟男性，声音沉稳有力"\n'
        '- "年轻女性，声音清脆悦耳，约25岁"\n'
        '- "专业新闻主播，声音清晰标准，语速适中"\n'
        '- "童话故事讲述者，声音温柔梦幻，略带神秘感"\n'
        '- "性格急躁的少年，声音清亮，语速偏快，充满活力"'
    )
    user_prompt = "请根据以下角色信息，生成音色描述提示词：\n\n" + "\n".join(character_lines) + "\n\n请直接输出音色描述："

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # 6. 调用 LLM（使用 asyncio.to_thread 包装同步调用）
    try:
        from llm.llm_client_factory import get_llm_client
        import asyncio

        llm_client = get_llm_client(model, vendor_id=vendor_id)
        response = await asyncio.to_thread(
            llm_client.call_api,
            model=model,
            messages=messages,
            temperature=RunningHubAudioConfig.AUDIO_STYLE_LLM_TEMPERATURE,
            max_tokens=RunningHubAudioConfig.AUDIO_STYLE_LLM_MAX_TOKENS,
        )

        result = response.choices[0].message.content.strip() if response and response.choices else ""

        if result:
            logger.info(f"LLM 生成音色描述成功: {result}")
            return result
        else:
            logger.warning("LLM 返回空内容，使用默认音色提示词")
            return RunningHubAudioConfig.AUDIO_STYLE_DEFAULT_PROMPT

    except Exception as e:
        logger.warning(f"LLM 生成音色描述失败，使用默认提示词: {e}")
        return RunningHubAudioConfig.AUDIO_STYLE_DEFAULT_PROMPT
