"""
Grok 通用聚合站点 v1 版本驱动实现
支持多个站点配置，使用基类+站点类的架构
"""
from typing import Dict, Any, Optional
import traceback
from .base_video_driver import BaseVideoDriver, ImageMode
from config.config_util import get_config, get_dynamic_config_value
from config.unified_config import DriverImplementation
from utils.sentry_util import SentryUtil, AlertLevel


class GrokCommonV1Driver(BaseVideoDriver):
    """
    Grok 通用聚合站点 v1 版本驱动（基类）
    对接 yunwu.ai 新接口 POST /v1/videos/generations，使用 grok-imagine-video 模型

    特点：
    - 支持多个站点配置（通过 site_id 区分）
    - 从 api_aggregator.{site_id} 加载配置
    - 支持首帧模式（image，单张）和多参考图模式（reference_images，最多7张）
    - 新接口 image 与 reference_images 互斥

    注意：这是基类，不应该直接实例化，应该使用具体的站点类
    """

    # Grok 模型名称（yunwu.ai 新接口）
    MODEL_NAME = "grok-imagine-video"

    # 固定分辨率（新接口必需字段，AITool 无该字段，固定 720p）
    RESOLUTION = "720p"

    # 默认时长（秒）
    DEFAULT_DURATION = 10

    # 多参考图模式最大图片数量
    MAX_REFERENCE_IMAGES = 7

    def __init__(self, site_id: str, impl_name: str = None):
        """
        初始化驱动（基类）

        Args:
            site_id: API 聚合站点ID（如 site_1, site_2, ... site_5）
                     对应配置 api_aggregator.site_X
            impl_name: 实现方名称，需与 IMPLEMENTATION_TO_ID 映射一致
        """
        self._site_id = site_id
        driver_name = impl_name or f"grok_common_{site_id}"
        super().__init__(driver_name=driver_name, driver_type=15)

        # 从 api_aggregator.{site_id} 加载配置
        self._api_key = get_dynamic_config_value("api_aggregator", site_id, "api_key", default="")
        self._base_url = get_dynamic_config_value("api_aggregator", site_id, "base_url", default="https://yunwu.ai")
        self._site_name = get_dynamic_config_value("api_aggregator", site_id, "name", default=site_id)
        self._timeout = get_dynamic_config_value("timeout", "request_timeout", default=30)

        # 是否为本地环境
        self._is_local = get_dynamic_config_value("server", "is_local", default=False)
        self._config = get_config()

        self._validate_required({
            f"API Aggregator {site_id} API Key": self._api_key,
        })

    def _send_alert(self, alert_type: str, message: str, context: Optional[Dict[str, Any]] = None):
        """
        发送报警信息

        Args:
            alert_type: 报警类型，如 "INVALID_RESPONSE_FORMAT", "UNEXPECTED_EXCEPTION"
            message: 报警消息
            context: 上下文信息（可选）
        """
        SentryUtil.send_alert(
            alert_type=alert_type,
            message=message,
            level=AlertLevel.ERROR,
            context=context
        )

    def _validate_submit_response(self, result: Any) -> tuple[bool, Optional[str]]:
        """
        验证 submit_task API 响应格式

        Args:
            result: API 响应结果

        Returns:
            tuple[bool, Optional[str]]: (是否有效, 错误信息)

        期望的响应格式（yunwu 新接口）:
        {
            "request_id": "86856ed7-xxxx-xxxx-xxxx"
        }
        同时兼容含 "id" 字段的旧风格格式
        """
        if not isinstance(result, dict):
            return False, f"响应不是字典类型，实际类型: {type(result)}"

        # 新接口返回 request_id，兼容旧风格的 id
        task_id = result.get("id") or result.get("request_id")
        if not task_id:
            return False, f"响应缺少 'id' 或 'request_id' 字段，实际字段: {list(result.keys())}"

        if not isinstance(task_id, str):
            return False, f"任务ID字段类型错误，期望 str，实际: {type(task_id)}"

        return True, None

    def _validate_status_response(self, result: Any) -> tuple[bool, Optional[str]]:
        """
        验证 check_status API 响应格式

        Args:
            result: API 响应结果

        Returns:
            tuple[bool, Optional[str]]: (是否有效, 错误信息)

        查询响应分阶段：
        - 早期（刚提交/排队中）：仅 {"request_id": "..."}，尚无 status
        - 处理中/完成/失败：{"id": "...", "status": "processing/completed/failed", "error": {...}}
        只要是合法 dict 即通过；具体状态由 check_status 解析（无 status 时兜底为 RUNNING）
        """
        if not isinstance(result, dict):
            return False, f"响应不是字典类型，实际类型: {type(result)}"

        return True, None

    def _map_aspect_ratio(self, ratio: str) -> str:
        """
        将视频比例映射为新接口支持的 aspect_ratio

        新接口仅支持 1:1 / 16:9 / 9:16，对其他比例做兜底映射：
        - 竖屏（2:3, 3:4）→ 9:16
        - 横屏（3:2, 4:3）→ 16:9
        - 其余未识别 → 9:16（默认）

        Args:
            ratio: 原始视频比例

        Returns:
            str: 新接口支持的 aspect_ratio
        """
        SUPPORTED = {"1:1", "16:9", "9:16"}
        if ratio in SUPPORTED:
            return ratio

        MAPPING = {
            "2:3": "9:16", "3:4": "9:16",   # 竖屏
            "3:2": "16:9", "4:3": "16:9",   # 横屏
        }
        mapped = MAPPING.get(ratio)
        if mapped:
            self.logger.warning(f"Grok yw新接口不支持比例 {ratio}，已映射为 {mapped}")
            return mapped

        self.logger.warning(f"Grok yw新接口不支持比例 {ratio}，使用默认 9:16")
        return "9:16"

    def build_create_request(self, ai_tool) -> Dict[str, Any]:
        """
        构建创建 Grok 任务的完整请求参数（对接 yunwu.ai 新接口）

        新接口 POST /v1/videos/generations，model/prompt/resolution/aspect_ratio/duration 必填，
        image 与 reference_images 互斥：
        - first_last_frame（首帧模式）：使用 image={url}，新接口 image 仅单张，忽略尾帧
        - multi_reference（多参模式）：使用 reference_images=[{url},...]，最多7张
        - first_last_with_ref：image 与 reference_images 互斥，优先使用首帧

        Args:
            ai_tool: AITool 对象

        Returns:
            Dict[str, Any]: 请求参数字典
        """
        # 解析图片模式
        image_info = self.get_all_images_by_mode(ai_tool)
        mode = image_info['mode']
        first_frame = image_info['first_frame']
        last_frame = image_info['last_frame']
        reference_images = image_info['reference_images']

        self.logger.info(f"Grok yw驱动图片模式: {mode}, 首帧: {first_frame}, 尾帧: {last_frame}, 参考图: {len(reference_images)}张")

        # 根据模式构建图片字段（新接口 image 单张对象 / reference_images 对象数组，二者互斥）
        image_url = None          # 首帧模式 -> image 字段（单张）
        ref_url_list = []         # 多参模式 -> reference_images 字段

        if mode == ImageMode.FIRST_LAST_FRAME:
            if first_frame:
                image_url = first_frame
            if last_frame:
                # 新接口 image 仅支持单张首帧，忽略尾帧
                self.logger.warning("Grok yw驱动首帧模式：新接口 image 仅支持单张，已忽略尾帧")
        elif mode == ImageMode.MULTI_REFERENCE:
            if reference_images:
                ref_url_list = reference_images[:self.MAX_REFERENCE_IMAGES]
                if len(reference_images) > self.MAX_REFERENCE_IMAGES:
                    self.logger.warning(f"Grok yw驱动最多支持{self.MAX_REFERENCE_IMAGES}张参考图，已截取")
        elif mode == ImageMode.FIRST_LAST_WITH_REF:
            # image 与 reference_images 互斥，优先使用首帧
            if first_frame:
                image_url = first_frame
                if reference_images:
                    self.logger.warning(f"Grok yw驱动首尾帧+参考图模式：已使用首帧，忽略 {len(reference_images)} 张参考图")
            elif reference_images:
                ref_url_list = reference_images[:self.MAX_REFERENCE_IMAGES]

        # 上传图片到CDN图床，确保外部API可访问（首帧在前，上传后按位置还原）
        all_urls = []
        if image_url:
            all_urls.append(image_url)
        all_urls.extend(ref_url_list)

        # grok 新接口要求 https 图片源，force_upload=True 强制把图片（含 http 外网源）重传到 https CDN
        if all_urls:
            uploaded = self.ensure_public_urls(all_urls, force_upload=True)
            if image_url:
                image_url = uploaded[0]
                ref_url_list = uploaded[1:]
            else:
                ref_url_list = uploaded

        # 比例映射为新接口支持的 aspect_ratio（1:1/16:9/9:16）
        ratio = getattr(ai_tool, 'ratio', None) or '9:16'
        aspect_ratio = self._map_aspect_ratio(ratio)

        # 时长：取合法档位（6/10/15），异常值回退默认，并做 [1,15] 边界防御
        duration = getattr(ai_tool, 'duration', None)
        try:
            duration = int(duration) if duration is not None else self.DEFAULT_DURATION
        except (TypeError, ValueError):
            duration = self.DEFAULT_DURATION
        if duration not in (6, 10, 15):
            self.logger.warning(f"Grok yw驱动时长 {duration} 不在支持档位(6/10/15)，回退默认 {self.DEFAULT_DURATION}")
            duration = self.DEFAULT_DURATION
        duration = max(1, min(15, duration))

        payload = {
            "model": self.MODEL_NAME,
            "prompt": ai_tool.prompt,
            "resolution": self.RESOLUTION,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
        }

        if image_url:
            payload["image"] = {"url": image_url}
        if ref_url_list:
            payload["reference_images"] = [{"url": u} for u in ref_url_list]

        return {
            "url": f"{self._base_url}/v1/videos/generations",
            "method": "POST",
            "json": payload,
            "headers": {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}"
            }
        }

    def build_check_query(self, project_id: str) -> Dict[str, Any]:
        """
        构建查询 Grok 任务状态的完整请求参数

        Args:
            project_id: 任务ID

        Returns:
            Dict[str, Any]: 请求参数字典
        """
        return {
            "url": f"{self._base_url}/v1/videos/{project_id}",
            "method": "GET",
            "json": None,
            "headers": {
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}"
            }
        }

    def submit_task(self, ai_tool) -> Dict[str, Any]:
        """
        提交 Grok 视频生成任务

        Args:
            ai_tool: AITool 对象
                - prompt: 提示词
                - ratio: 视频比例
                - image_path: 图片路径

        Returns:
            Dict[str, Any]: 提交结果
        """
        try:
            self.logger.info(f"Submitting Grok yunwu task: prompt='{ai_tool.prompt[:50]}...'")

            # 构建请求参数
            request_params = self.build_create_request(ai_tool)

            # 调用统一请求方法
            try:
                result = self._request(**request_params)
            except (ConnectionError, TimeoutError) as network_error:
                self.logger.warning(f"Network error during Grok yunwu task submission: {str(network_error)}")
                return {
                    "success": False,
                    "error": "网络连接异常，请稍后重试",
                    "error_type": "USER",
                    "retry": True
                }

            self.logger.info(f"Grok yunwu API response: {result}")

            # 验证响应格式
            is_valid, validation_error = self._validate_submit_response(result)
            if not is_valid:
                self._send_alert(
                    alert_type="INVALID_RESPONSE_FORMAT",
                    message=f"Grok yunwu submit_task 响应格式错误: {validation_error}",
                    context={
                        "api": "v1/videos/generations",
                        "response": result,
                        "ai_tool_id": ai_tool.id
                    }
                )
                return {
                    "success": False,
                    "error": "服务异常，请联系技术支持",
                    "error_type": "SYSTEM",
                    "error_detail": f"API响应格式错误: {validation_error}",
                    "retry": False
                }

            project_id = result.get("id") or result.get("request_id")
            if not project_id:
                return {
                    "success": False,
                    "error": "服务异常，请联系技术支持",
                    "error_type": "SYSTEM",
                    "error_detail": "Grok yunwu API未返回任务ID",
                    "retry": False
                }

            return {
                "success": True,
                "project_id": project_id
            }

        except Exception as e:
            self.logger.error(f"Unexpected exception in Grok yunwu submit_task: {str(e)}")
            self.logger.error(traceback.format_exc())

            self._send_alert(
                alert_type="UNEXPECTED_EXCEPTION",
                message=f"Grok yunwu submit_task 发生未预期异常: {str(e)}",
                context={
                    "exception": str(e),
                    "traceback": traceback.format_exc(),
                    "ai_tool_id": ai_tool.id
                }
            )

            return {
                "success": False,
                "error": "服务异常，请联系技术支持",
                "error_type": "SYSTEM",
                "error_detail": f"未预期异常: {str(e)}",
                "retry": False
            }

    def check_status(self, project_id: str) -> Dict[str, Any]:
        """
        检查 Grok 任务状态

        Args:
            project_id: 任务ID

        Returns:
            Dict[str, Any]: 状态检查结果
        """
        try:
            self.logger.info(f"Checking Grok yunwu task status: project_id={project_id}")

            # 构建请求参数并调用统一请求方法
            request_params = self.build_check_query(project_id)

            try:
                raw_result = self._request(**request_params)
            except (ConnectionError, TimeoutError) as network_error:
                self.logger.warning(f"Network error during Grok yunwu status check: {str(network_error)}")
                return {
                    "status": "RUNNING",
                    "message": "网络连接异常，稍后将重试"
                }

            self.logger.info(f"Grok yunwu status API response: {raw_result}")

            # 验证响应格式
            is_valid, validation_error = self._validate_status_response(raw_result)
            if not is_valid:
                self._send_alert(
                    alert_type="INVALID_RESPONSE_FORMAT",
                    message=f"Grok yunwu check_status 响应格式错误: {validation_error}",
                    context={
                        "api": "v1/videos/{request_id}",
                        "response": raw_result,
                        "project_id": project_id
                    }
                )
                return {
                    "status": "FAILED",
                    "error": "服务异常，请联系技术支持",
                    "error_type": "SYSTEM",
                    "error_detail": f"API响应格式错误: {validation_error}"
                }

            # 解析状态 - 适配 OpenAI 风格或直接状态字段
            # 尝试多种响应格式
            status_value = raw_result.get("status", "")
            result_data = raw_result

            # 格式1: 直接 status 字段 (done / completed / processing / failed)
            if status_value:
                if status_value in ("completed", "COMPLETED", "success", "SUCCESS", "done", "DONE", "succeeded", "Succeeded"):
                    # 尝试从 output.video.url 或 choices 中提取视频URL
                    video_url = self._extract_video_url(result_data)
                    if video_url:
                        return {
                            "status": "SUCCESS",
                            "result_url": video_url
                        }
                    else:
                        return {
                            "status": "FAILED",
                            "error": "任务完成但未找到视频URL",
                            "error_type": "SYSTEM"
                        }
                elif status_value in ("failed", "FAILED", "error", "ERROR"):
                    error = raw_result.get("error", raw_result.get("message", "任务失败"))
                    # error 可能是字符串，也可能是 {"code": ..., "message": ...} 字典
                    if isinstance(error, dict):
                        error_msg = error.get("message") or error.get("code") or str(error)
                    else:
                        error_msg = error
                    return {
                        "status": "FAILED",
                        "error": error_msg,
                        "error_type": "USER"
                    }
                else:
                    # processing / in_queue / in_progress 等
                    return {
                        "status": "RUNNING",
                        "message": "任务处理中..."
                    }

            # 格式2: OpenAI choices 风格
            choices = raw_result.get("choices", [])
            if choices:
                choice = choices[0]
                message = choice.get("message", {})
                content = message.get("content", "")
                finish_reason = choice.get("finish_reason", "")

                if finish_reason == "stop" and content:
                    # 可能 content 就是视频URL，或者需要解析
                    return {
                        "status": "SUCCESS",
                        "result_url": content
                    }
                elif finish_reason == "error":
                    return {
                        "status": "FAILED",
                        "error": content or "任务失败",
                        "error_type": "USER"
                    }
                else:
                    return {
                        "status": "RUNNING",
                        "message": "任务处理中..."
                    }

            # 无 status 字段（早期刚提交/排队中，仅含 request_id）→ 视为处理中（正常，非异常）
            self.logger.info(f"任务尚无 status，视为排队/处理中: {raw_result}")
            return {
                "status": "RUNNING",
                "message": "任务处理中..."
            }

        except Exception as e:
            self.logger.error(f"Unexpected exception in Grok yunwu check_status: {str(e)}")
            self.logger.error(traceback.format_exc())

            self._send_alert(
                alert_type="UNEXPECTED_EXCEPTION",
                message=f"Grok yunwu check_status 发生未预期异常: {str(e)}",
                context={
                    "exception": str(e),
                    "traceback": traceback.format_exc(),
                    "project_id": project_id
                }
            )

            return {
                "status": "FAILED",
                "error": "服务异常，请联系技术支持",
                "error_type": "SYSTEM",
                "error_detail": f"未预期异常: {str(e)}"
            }

    def _extract_video_url(self, data: dict) -> Optional[str]:
        """
        从响应数据中提取视频URL
        尝试多种可能的路径

        Args:
            data: 响应数据

        Returns:
            视频URL或None
        """
        # 路径0: detail.video_url
        detail = data.get("detail", {})
        if isinstance(detail, dict):
            url = detail.get("video_url")
            if url:
                return url

        # 路径1: output.video.url
        output = data.get("output", {})
        if isinstance(output, dict):
            video = output.get("video", {})
            if isinstance(video, dict):
                url = video.get("url")
                if url:
                    return url

        # 路径2: data.video.url
        result_data = data.get("data", {})
        if isinstance(result_data, dict):
            video = result_data.get("video", {})
            if isinstance(video, dict):
                url = video.get("url")
                if url:
                    return url
            # 路径3: data.mediaUrl
            media_url = result_data.get("mediaUrl")
            if media_url:
                return media_url

        # 路径4: 直接 video.url
        video = data.get("video", {})
        if isinstance(video, dict):
            url = video.get("url")
            if url:
                return url

        # 路径5: choices[0].message.content
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content and (content.startswith("http://") or content.startswith("https://")):
                return content

        # 路径6: 根级别 video_url
        url = data.get("video_url")
        if url:
            return url

        # 路径7: output.url / data.url（yunwu 等新接口视频 url 可能直接挂这层）
        if isinstance(output, dict) and output.get("url"):
            return output["url"]
        if isinstance(result_data, dict) and result_data.get("url"):
            return result_data["url"]

        # 路径8: 根级 url
        url = data.get("url")
        if url:
            return url

        return None


# ============ 具体站点实现类 ============

class GrokCommonSite0V1Driver(GrokCommonV1Driver):
    """Grok 通用聚合 Site 0 v1 版本驱动"""

    def __init__(self):
        super().__init__(site_id="site_0", impl_name=DriverImplementation.GROK_COMMON_SITE0_V1)


class GrokCommonSite1V1Driver(GrokCommonV1Driver):
    """Grok 通用聚合 Site 1 v1 版本驱动"""

    def __init__(self):
        super().__init__(site_id="site_1", impl_name=DriverImplementation.GROK_COMMON_SITE1_V1)


class GrokCommonSite2V1Driver(GrokCommonV1Driver):
    """Grok 通用聚合 Site 2 v1 版本驱动"""

    def __init__(self):
        super().__init__(site_id="site_2", impl_name=DriverImplementation.GROK_COMMON_SITE2_V1)


class GrokCommonSite3V1Driver(GrokCommonV1Driver):
    """Grok 通用聚合 Site 3 v1 版本驱动"""

    def __init__(self):
        super().__init__(site_id="site_3", impl_name=DriverImplementation.GROK_COMMON_SITE3_V1)


class GrokCommonSite4V1Driver(GrokCommonV1Driver):
    """Grok 通用聚合 Site 4 v1 版本驱动"""

    def __init__(self):
        super().__init__(site_id="site_4", impl_name=DriverImplementation.GROK_COMMON_SITE4_V1)


class GrokCommonSite5V1Driver(GrokCommonV1Driver):
    """Grok 通用聚合 Site 5 v1 版本驱动"""

    def __init__(self):
        super().__init__(site_id="site_5", impl_name=DriverImplementation.GROK_COMMON_SITE5_V1)
