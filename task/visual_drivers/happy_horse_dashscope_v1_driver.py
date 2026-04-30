"""
Happy Horse 阿里云百炼驱动实现
模型: happyhorse-1.0-i2v
支持图生视频（基于首帧），异步任务模式
"""
from typing import Dict, Any, Optional
import traceback
import json
from .base_video_driver import BaseVideoDriver, ImageMode
from config.config_util import get_config, get_dynamic_config_value
from utils.sentry_util import SentryUtil, AlertLevel
from utils.image_upload_utils import upload_local_images_to_cdn_sync


class HappyHorseDashscopeV1Driver(BaseVideoDriver):
    """
    Happy Horse 图生视频驱动（阿里云百炼 DashScope）
    支持单张首帧图片 + 可选的驱动音频和驱动视频
    """

    def __init__(self):
        super().__init__(driver_name="happy_horse_dashscope_v1", driver_type=28)

        # 加载配置
        self._api_key = get_dynamic_config_value("dashscope", "api_key", default="")
        self._base_url = "https://dashscope.aliyuncs.com/api/v1"
        self._timeout = get_dynamic_config_value("timeout", "request_timeout", default=30)

        # 是否为本地环境
        self._is_local = get_dynamic_config_value("server", "is_local", default=False)
        self._config = get_config()

        self._validate_required({
            "DashScope API Key": self._api_key,
        })

    def _send_alert(self, alert_type: str, message: str, context: Optional[Dict[str, Any]] = None):
        """
        发送报警信息
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

        期望响应:
        {
            "output": {
                "task_status": "PENDING",
                "task_id": "0385dc79-5ff8-4d82-bcb6-xxxxxx"
            },
            "request_id": "..."
        }
        """
        if not isinstance(result, dict):
            return False, f"响应不是字典类型，实际类型: {type(result)}"

        if "error" in result:
            return True, None  # 有错误字段，格式有效但业务失败

        output = result.get("output")
        if not isinstance(output, dict):
            return False, f"响应缺少 'output' 字段或类型错误，实际: {result.keys()}"

        if "task_id" not in output:
            return False, f"output 缺少 'task_id' 字段"

        return True, None

    def _validate_status_response(self, result: Any) -> tuple[bool, Optional[str]]:
        """
        验证 check_status API 响应格式

        期望响应:
        {
            "output": {
                "task_id": "...",
                "task_status": "SUCCEEDED",
                "video_url": "https://..."
            },
            "request_id": "..."
        }
        """
        if not isinstance(result, dict):
            return False, f"响应不是字典类型，实际类型: {type(result)}"

        if "error" in result:
            return True, None

        output = result.get("output")
        if not isinstance(output, dict):
            return False, f"响应缺少 'output' 字段或类型错误"

        if "task_status" not in output:
            return False, f"output 缺少 'task_status' 字段"

        return True, None

    def _parse_extra_params(self, ai_tool) -> Dict[str, Any]:
        """
        从 extra_config 解析可选参数
        支持: resolution (720P/1080P), watermark (true/false), seed (int)
        """
        params = {
            "resolution": "1080P",  # 默认值
            "watermark": True,      # 默认添加水印
        }

        if not ai_tool.extra_config:
            return params

        try:
            config = json.loads(ai_tool.extra_config) if isinstance(ai_tool.extra_config, str) else ai_tool.extra_config
            if isinstance(config, dict):
                if "resolution" in config and config["resolution"] in ("720P", "1080P"):
                    params["resolution"] = config["resolution"]
                if "watermark" in config:
                    params["watermark"] = bool(config["watermark"])
                if "seed" in config:
                    seed = config["seed"]
                    if isinstance(seed, int) and 0 <= seed <= 2147483647:
                        params["seed"] = seed
        except (json.JSONDecodeError, TypeError, ValueError):
            self.logger.warning(f"无法解析 extra_config: {ai_tool.extra_config}")

        return params

    def _upload_media_to_cdn(self, media_urls: List[str], media_type: str = "媒体") -> List[str]:
        """
        将本地媒体文件上传到图床

        Args:
            media_urls: 媒体文件路径或URL列表
            media_type: 媒体类型描述（用于日志）

        Returns:
            List[str]: 上传后的CDN链接列表
        """
        if not media_urls:
            return media_urls

        if self._is_local:
            self.logger.info(f"本地环境检测到{media_type}路径，准备上传到图床: {media_urls}")
            result = upload_local_images_to_cdn_sync(media_urls, self._config)
            self.logger.info(f"{media_type}上传完成，CDN链接: {result}")
            return result

        return media_urls

    def build_create_request(self, ai_tool) -> Dict[str, Any]:
        """
        构建创建 Happy Horse 任务的完整请求参数

        支持：
        - 首帧图片（有且仅有1张，必须）
        - 驱动音频（可选，type=driving_audio）
        - 驱动视频（可选，type=driving_video）
        ratio 由 API 从首帧自动推断
        """
        # 获取首帧图片（仅取第一张）
        first_frame, _ = self.get_first_last_frames(ai_tool)

        if not first_frame:
            return {
                "success": False,
                "error": "缺少首帧图片",
                "error_type": "USER",
                "retry": False
            }

        # 处理首帧图片上传
        image_urls = self._upload_media_to_cdn([first_frame], "图片")
        first_frame_url = image_urls[0]

        # 构建 media 列表
        media_list = [
            {
                "type": "first_frame",
                "url": first_frame_url
            }
        ]

        # 处理驱动音频
        audio_path = self.get_audio_path(ai_tool)
        if audio_path:
            audio_urls = self._upload_media_to_cdn([audio_path], "音频")
            if audio_urls and audio_urls[0]:
                media_list.append({
                    "type": "driving_audio",
                    "url": audio_urls[0]
                })
                self.logger.info(f"已添加驱动音频: {audio_urls[0]}")

        # 处理驱动视频
        video_path = self.get_video_path(ai_tool)
        if video_path:
            video_urls = self._upload_media_to_cdn([video_path], "视频")
            if video_urls and video_urls[0]:
                media_list.append({
                    "type": "driving_video",
                    "url": video_urls[0]
                })
                self.logger.info(f"已添加驱动视频: {video_urls[0]}")

        # 解析 extra_config 中的可选参数
        extra_params = self._parse_extra_params(ai_tool)

        # 构建请求体
        duration = ai_tool.duration or 5
        if not (3 <= duration <= 15):
            duration = 5

        payload = {
            "model": "happyhorse-1.0-i2v",
            "input": {
                "prompt": ai_tool.prompt or "",
                "media": media_list
            },
            "parameters": {
                "resolution": extra_params["resolution"],
                "duration": duration,
                "watermark": extra_params["watermark"]
            }
        }

        # 可选参数：seed
        if "seed" in extra_params:
            payload["parameters"]["seed"] = extra_params["seed"]

        return {
            "url": f"{self._base_url}/services/aigc/video-generation/video-synthesis",
            "method": "POST",
            "json": payload,
            "headers": {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "X-DashScope-Async": "enable"
            },
            "timeout": self._timeout
        }

    def build_check_query(self, project_id: str) -> Dict[str, Any]:
        """
        构建查询 Happy Horse 任务状态的完整请求参数
        """
        return {
            "url": f"{self._base_url}/tasks/{project_id}",
            "method": "GET",
            "headers": {
                "Authorization": f"Bearer {self._api_key}"
            },
            "timeout": self._timeout
        }

    def submit_task(self, ai_tool) -> Dict[str, Any]:
        """
        提交 Happy Horse 视频生成任务
        """
        try:
            # 验证首帧图片
            first_frame, _ = self.get_first_last_frames(ai_tool)
            if not first_frame:
                return {
                    "success": False,
                    "error": "缺少首帧图片",
                    "error_type": "USER",
                    "retry": False
                }

            audio_path = self.get_audio_path(ai_tool)
            video_path = self.get_video_path(ai_tool)
            self.logger.info(
                f"Submitting Happy Horse task: prompt='{(ai_tool.prompt or '')[:50]}...', "
                f"duration={ai_tool.duration}, first_frame={first_frame}, "
                f"audio={audio_path is not None}, video={video_path is not None}"
            )

            # 构建请求参数
            request_params = self.build_create_request(ai_tool)
            if "success" in request_params and not request_params["success"]:
                return request_params

            # 调用统一请求方法
            try:
                result = self._request(**request_params)
            except (ConnectionError, TimeoutError) as network_error:
                self.logger.warning(f"Network error during Happy Horse task submission: {str(network_error)}")
                return {
                    "success": False,
                    "error": "网络连接异常，请稍后重试",
                    "error_type": "USER",
                    "retry": True
                }

            self.logger.info(f"Happy Horse API response: {result}")

            # 验证响应格式
            is_valid, validation_error = self._validate_submit_response(result)
            if not is_valid:
                self._send_alert(
                    alert_type="INVALID_RESPONSE_FORMAT",
                    message=f"Happy Horse submit_task 响应格式错误: {validation_error}",
                    context={
                        "api": "create_happy_horse_video",
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

            # 检查业务错误
            if "error" in result:
                error_code = result.get("error", {})
                error_msg = "未知错误"
                if isinstance(error_code, dict):
                    error_msg = error_code.get("message", str(error_code))
                else:
                    error_msg = str(error_code)
                self.logger.warning(f"Happy Horse API returned error: {error_msg}")
                return {
                    "success": False,
                    "error": f"任务提交失败: {error_msg}",
                    "error_type": "USER",
                    "retry": False
                }

            # 提取任务ID
            output = result.get("output", {})
            task_id = output.get("task_id")
            if not task_id:
                self._send_alert(
                    alert_type="MISSING_TASK_ID",
                    message="Happy Horse submit_task 响应缺少 task_id",
                    context={
                        "api": "create_happy_horse_video",
                        "response": result,
                        "ai_tool_id": ai_tool.id
                    }
                )
                return {
                    "success": False,
                    "error": "服务异常，请联系技术支持",
                    "error_type": "SYSTEM",
                    "error_detail": "API未返回任务ID",
                    "retry": False
                }

            return {
                "success": True,
                "project_id": task_id
            }

        except Exception as e:
            self.logger.error(f"Unexpected exception in Happy Horse submit_task: {str(e)}")
            self.logger.error(traceback.format_exc())

            self._send_alert(
                alert_type="UNEXPECTED_EXCEPTION",
                message=f"Happy Horse submit_task 发生未预期异常: {str(e)}",
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
        检查 Happy Horse 任务状态
        """
        try:
            self.logger.info(f"Checking Happy Horse task status: project_id={project_id}")

            # 构建请求参数并调用统一请求方法
            request_params = self.build_check_query(project_id)

            try:
                result = self._request(**request_params)
            except (ConnectionError, TimeoutError) as network_error:
                self.logger.warning(f"Network error during Happy Horse status check: {str(network_error)}")
                return {
                    "status": "RUNNING",
                    "message": "网络连接异常，稍后将重试"
                }

            self.logger.info(f"Happy Horse status API response: {result}")

            # 验证响应格式
            is_valid, validation_error = self._validate_status_response(result)
            if not is_valid:
                self._send_alert(
                    alert_type="INVALID_RESPONSE_FORMAT",
                    message=f"Happy Horse check_status 响应格式错误: {validation_error}",
                    context={
                        "api": "get_happy_horse_task_status",
                        "response": result,
                        "project_id": project_id
                    }
                )
                return {
                    "status": "FAILED",
                    "error": "服务异常，请联系技术支持",
                    "error_type": "SYSTEM",
                    "error_detail": f"API响应格式错误: {validation_error}"
                }

            # 检查业务错误
            if "error" in result:
                error_code = result.get("error", {})
                error_msg = "未知错误"
                if isinstance(error_code, dict):
                    error_msg = error_code.get("message", str(error_code))
                else:
                    error_msg = str(error_code)
                self.logger.warning(f"Happy Horse status API returned error: {error_msg}")
                return {
                    "status": "FAILED",
                    "error": f"查询任务状态失败: {error_msg}",
                    "error_type": "USER"
                }

            # 提取状态
            output = result.get("output", {})
            task_status = output.get("task_status", "UNKNOWN")

            # 映射状态到统一状态
            if task_status == "SUCCEEDED":
                video_url = output.get("video_url")
                if video_url:
                    return {
                        "status": "SUCCESS",
                        "result_url": video_url
                    }
                else:
                    return {
                        "status": "FAILED",
                        "error": "任务成功但未返回视频URL",
                        "error_type": "SYSTEM"
                    }
            elif task_status == "FAILED":
                error_code = output.get("code", "任务执行失败")
                error_message = output.get("message", error_code)
                return {
                    "status": "FAILED",
                    "error": error_message,
                    "error_type": "USER"
                }
            elif task_status == "CANCELED":
                return {
                    "status": "FAILED",
                    "error": "任务已取消",
                    "error_type": "USER"
                }
            elif task_status == "UNKNOWN":
                return {
                    "status": "FAILED",
                    "error": "任务不存在或已过期",
                    "error_type": "USER"
                }
            elif task_status in ("PENDING", "RUNNING"):
                return {
                    "status": "RUNNING",
                    "message": f"任务{task_status == 'PENDING' and '排队中' or '处理中'}..."
                }
            else:
                self.logger.warning(f"Unknown Happy Horse task status: {task_status}")
                return {
                    "status": "RUNNING",
                    "message": f"任务状态: {task_status}"
                }

        except Exception as e:
            self.logger.error(f"Unexpected exception in Happy Horse check_status: {str(e)}")
            self.logger.error(traceback.format_exc())

            self._send_alert(
                alert_type="UNEXPECTED_EXCEPTION",
                message=f"Happy Horse check_status 发生未预期异常: {str(e)}",
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
