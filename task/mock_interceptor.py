"""
E2E 测试挡板拦截器（纯逻辑层）。

当 test_mode.enabled=True 时，拦截所有外部媒体生成调用，返回预设本地媒体。
本模块只负责"判断与构造响应"，写库由各通道调度器复用现有成功处理函数完成。

设计要点（详见 docs/e2e_mock_implementation_plan.md）：
- mock project_id 统一前缀 mock_task_，轮询/重试调度器据此识别并短路。
- mock 资源一律本地 /upload/mock/... 真实文件。
- TaskCategory 是字符串常量类（非 Enum），值如 'text_to_image'/'image_edit'，
  解析 mock URL 时优先按主分类 cfg.category 精确映射，categories 仅作兜底。
"""
import logging
import threading
import uuid
from typing import Any, Dict, Optional

from config.config_util import get_dynamic_config_value
from config.unified_config import UnifiedConfigRegistry, TaskCategory

logger = logging.getLogger(__name__)

MOCK_PROJECT_PREFIX = "mock_task_"

# ============ 进程内命中计数（可观测性） ============
_counters_lock = threading.Lock()
_counters: Dict[str, int] = {}


def _bump(channel: str) -> None:
    with _counters_lock:
        _counters[channel] = _counters.get(channel, 0) + 1


def mock_hit_summary() -> Dict[str, int]:
    """返回各通道 mock 命中计数（E2E 结束时打印，判断是否仍有路径漏到真实外部服务）。"""
    with _counters_lock:
        return dict(_counters)


# ============ 开关与 ID ============
def is_mock_enabled() -> bool:
    """挡板总开关。注意：受 _DYNAMIC_CACHE_TTL=30s 缓存影响，跨进程有传播延迟（见方案 §7）。"""
    return bool(get_dynamic_config_value("test_mode", "enabled", default=False))


def generate_mock_project_id() -> str:
    return f"{MOCK_PROJECT_PREFIX}{uuid.uuid4().hex[:16]}"


def is_mock_id(task_id: Optional[str]) -> bool:
    return isinstance(task_id, str) and task_id.startswith(MOCK_PROJECT_PREFIX)


# ============ 按 category 解析 mock URL ============
def _img(key: str) -> Optional[str]:
    return get_dynamic_config_value("test_mode", "mock_images", key, default=None)


def _vid(key: str) -> Optional[str]:
    return get_dynamic_config_value("test_mode", "mock_videos", key, default=None)


def _aud(key: str) -> Optional[str]:
    return get_dynamic_config_value("test_mode", "mock_audio", key, default=None)


def mock_image(subkey: str = "text_to_image") -> Optional[str]:
    return _img(subkey)


def mock_video(subkey: str = "image_to_video") -> Optional[str]:
    return _vid(subkey)


def mock_audio(subkey: str = "tts") -> Optional[str]:
    return _aud(subkey)


def resolve_mock_url_for_visual(ai_tool_type: int) -> Optional[str]:
    """
    根据 ai_tool.type 解析视觉任务的 mock URL。
    优先按主分类(cfg.category)精确映射，再用 categories 兜底——
    否则图编模型(category=IMAGE_EDIT, categories=[TEXT_TO_IMAGE])会被误判为文生图。
    """
    try:
        cfg = UnifiedConfigRegistry.get_by_id(ai_tool_type)
        if not cfg:
            return None
        primary = cfg.category
        cats = [primary] + list(cfg.categories or [])

        def pick(*candidates, getter):
            for c in candidates:
                if c in cats:
                    url = getter(c)
                    if url:
                        return url
            return None

        # 视频（数字人归视频桶）
        url = pick(TaskCategory.IMAGE_TO_VIDEO, TaskCategory.TEXT_TO_VIDEO,
                   TaskCategory.DIGITAL_HUMAN, getter=_vid)
        if url:
            return url
        # 图片：优先主分类
        if primary == TaskCategory.IMAGE_EDIT:
            url = _img("image_edit")
        elif primary == TaskCategory.TEXT_TO_IMAGE:
            url = _img("text_to_image")
        else:
            url = pick(TaskCategory.TEXT_TO_IMAGE, TaskCategory.IMAGE_EDIT, getter=_img)
        if url:
            return url
        # 兜底
        return _vid("image_to_video") or _img("text_to_image")
    except Exception as e:
        logger.warning(f"[MOCK] resolve_mock_url_for_visual({ai_tool_type}) failed: {e}")
        return None


# ============ 各通道响应结构构造 ============
def visual_async_submit_result(ai_tool_type: int) -> Dict[str, Any]:
    """视觉异步：submit 返回 project_id，check_status 稍后返回 SUCCESS+url。"""
    _bump("visual_async_submit")
    pid = generate_mock_project_id()
    logger.info(f"[MOCK] channel=visual_async_submit type={ai_tool_type} project_id={pid}")
    return {"success": True, "project_id": pid}


def visual_async_status_result(ai_tool_type: int) -> Dict[str, Any]:
    """视觉异步：check_status 直接返回 SUCCESS。"""
    url = resolve_mock_url_for_visual(ai_tool_type)
    _bump("visual_async_poll")
    logger.info(f"[MOCK] channel=visual_async_poll type={ai_tool_type} url={url}")
    return {"status": "SUCCESS", "result_url": url}


def visual_sync_result(ai_tool_type: int) -> Dict[str, Any]:
    """视觉同步：返回 sync_mode 结果。"""
    url = resolve_mock_url_for_visual(ai_tool_type)
    _bump("visual_sync_submit")
    logger.info(f"[MOCK] channel=visual_sync_submit type={ai_tool_type} url={url}")
    return {"success": True, "sync_mode": True, "result_url": url}


def comfyui_submit_result(ai_tool_type: int) -> Dict[str, Any]:
    """ComfyUI 工具直调 submit：兼容 {project_ids, status} 结构。"""
    _bump("comfyui_submit")
    pid = generate_mock_project_id()
    logger.info(f"[MOCK] channel=comfyui_submit type={ai_tool_type} project_id={pid}")
    return {"status": "submitted", "project_ids": [pid]}


def comfyui_status_success(file_url: str) -> Dict[str, Any]:
    """ComfyUI 轮询成功：返回 tasks[0] 元素结构（含 results[0].file_url）。
    注意：grid_image_task._handle_task_success 接收的是 tasks[0] 元素本身，不是外层 envelope。"""
    _bump("comfyui_poll")
    logger.info(f"[MOCK] channel=comfyui_poll file_url={file_url}")
    return {
        "status": "SUCCESS",
        "results": [{"file_url": file_url, "result_url": file_url,
                     "cdn_status": "skip", "task_cost_time": 0}],
    }


def async_submit_result(impl_label: str) -> Dict[str, Any]:
    """RunningHub 异步（音频/人脸遮盖）：submit 返回 mock project_id。"""
    _bump(f"async_submit:{impl_label}")
    pid = generate_mock_project_id()
    logger.info(f"[MOCK] channel=async_submit impl={impl_label} project_id={pid}")
    return {"success": True, "project_id": pid}
