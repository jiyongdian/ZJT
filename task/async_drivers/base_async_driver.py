"""
异步驱动抽象基类
所有异步驱动都需要继承此基类并实现其抽象方法。
与 BaseVideoDriver（同步驱动）对应，适用于需要异步非阻塞调用的场景。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import traceback
from datetime import datetime
import httpx
from utils.logger_config import DailyFileHandler

logger = logging.getLogger(__name__)


def _setup_async_api_logger():
    """设置异步 API 请求日志记录器"""
    api_logger = logging.getLogger("async_api_requests")
    if not api_logger.handlers:
        file_handler = DailyFileHandler('async_api_requests', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        api_logger.addHandler(file_handler)
        api_logger.setLevel(logging.INFO)
    return api_logger


api_logger = _setup_async_api_logger()


class BaseAsyncDriver(ABC):
    """
    异步驱动抽象基类

    所有异步驱动必须继承此类并实现以下方法：
    - submit_task: 异步提交任务到外部API
    - check_status: 异步检查任务状态
    """

    def __init__(self, driver_name: str):
        """
        初始化异步驱动

        Args:
            driver_name: 驱动名称，如 "runninghub_audio" 等
        """
        self.driver_name = driver_name
        self.logger = logging.getLogger(f"{__name__}.{driver_name}")

    @abstractmethod
    async def submit_task(self, **kwargs) -> Dict[str, Any]:
        """
        异步提交任务到外部API

        Returns:
            Dict[str, Any]: 返回结果字典
                成功时包含:
                    - success: True
                    - project_id: 外部API返回的任务ID
                失败时包含:
                    - success: False
                    - error: 错误信息（用户可见的友好提示）
                    - error_type: 错误类型，"USER" 或 "SYSTEM"
                    - error_detail: 详细错误信息（仅 error_type="SYSTEM" 时）
                    - retry: 是否需要重试（可选，默认False）
        """
        pass

    @abstractmethod
    async def check_status(self, project_id: str) -> Dict[str, Any]:
        """
        异步查询任务状态

        Args:
            project_id: 外部API返回的任务ID

        Returns:
            Dict[str, Any]: 返回结果字典
                - status: 任务状态 ("RUNNING" | "SUCCESS" | "FAILED")
                - result_url: 结果URL（status为SUCCESS时）
                - error: 错误信息（status为FAILED时）
                - error_type: 错误类型（status为FAILED时）
        """
        pass

    async def _request(
        self,
        url: str,
        method: str = "POST",
        json: dict = None,
        headers: dict = None,
        timeout: float = 30,
        **kwargs
    ) -> dict:
        """
        统一异步 HTTP 请求方法。所有外部 API 调用都通过此方法。
        请求和响应会记录到日志。

        Args:
            url: 请求URL
            method: HTTP方法，默认POST
            json: 请求体（JSON格式）
            headers: 请求头
            timeout: 超时时间（秒）

        Returns:
            dict: API响应的JSON数据

        Raises:
            ConnectionError: 连接失败
            TimeoutError: 请求超时
        """
        request_time = datetime.now().isoformat()
        api_logger.info(f"========== 异步 API 请求开始 ==========")
        api_logger.info(f"Driver: {self.driver_name}")
        api_logger.info(f"Time: {request_time}")
        api_logger.info(f"Method: {method}")
        api_logger.info(f"URL: {url}")
        api_logger.info(f"Headers: {self._mask_sensitive_headers(headers)}")
        api_logger.info(f"Payload: {self._mask_sensitive_payload(json)}")

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method, url, json=json, headers=headers, **kwargs
                )

            response_time = datetime.now().isoformat()
            api_logger.info(f"Response Time: {response_time}")
            api_logger.info(f"Status Code: {response.status_code}")

            try:
                result = response.json()
                api_logger.info(f"Response Body: {self._truncate_base64_in_response(result)}")
            except Exception:
                result = {}
                api_logger.info(f"Response Body (raw): {response.text[:1000]}")

            api_logger.info(f"========== 异步 API 请求结束 ==========")
            response.raise_for_status()
            return result

        except httpx.TimeoutException as e:
            api_logger.error(f"Request Timeout: {str(e)}")
            api_logger.info(f"========== 异步 API 请求超时 ==========")
            raise TimeoutError(str(e)) from e
        except httpx.ConnectError as e:
            api_logger.error(f"Connection Error: {str(e)}")
            api_logger.info(f"========== 异步 API 请求连接失败 ==========")
            raise ConnectionError(str(e)) from e
        except httpx.HTTPStatusError as e:
            api_logger.error(f"HTTP Error: {e.response.status_code}")
            api_logger.info(f"========== 异步 API 请求失败 ==========")
            raise
        except Exception as e:
            api_logger.error(f"Request Error: {str(e)}")
            api_logger.error(f"Traceback: {traceback.format_exc()}")
            api_logger.info(f"========== 异步 API 请求失败 ==========")
            raise

    # ==================== 日志脱敏工具方法 ====================

    def _mask_sensitive_headers(self, headers: dict) -> dict:
        """脱敏请求头中的敏感信息"""
        if not headers:
            return {}
        masked = headers.copy()
        for key in masked:
            if key.lower() in ["authorization", "x-api-key", "api-key"]:
                value = masked[key]
                if len(value) > 20:
                    masked[key] = value[:10] + "***" + value[-4:]
                else:
                    masked[key] = "***"
        return masked

    def _mask_sensitive_payload(self, payload: dict) -> dict:
        """脱敏请求体中的敏感信息（递归处理嵌套字典）"""
        if not payload:
            return {}
        sensitive_keys = ["apikey", "api_key", "secret", "password", "token", "key"]
        masked = {}
        for key, value in payload.items():
            if key.lower() in sensitive_keys:
                str_value = str(value)
                if len(str_value) > 10:
                    masked[key] = str_value[:4] + "***" + str_value[-4:]
                else:
                    masked[key] = "***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_payload(value)
            elif isinstance(value, list):
                masked[key] = [self._mask_sensitive_payload(item) if isinstance(item, dict) else item for item in value]
            else:
                masked[key] = value
        return masked

    def _truncate_base64_in_response(self, data: Any, max_length: int = 50) -> Any:
        """精简响应体中的 base64 数据和大型字段"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if key == "inlineData" and isinstance(value, dict):
                    result[key] = {"mimeType": value.get("mimeType", "unknown"), "data": "[base64 image data masked]"}
                elif key == "data" and isinstance(value, str) and len(value) > max_length:
                    if all(c.isalnum() or c in '+/=' for c in value[:100]):
                        result[key] = f"[base64 data {len(value)} chars masked]"
                    else:
                        result[key] = value
                elif key == "b64_json" and isinstance(value, str) and len(value) > max_length:
                    result[key] = "[b64_json masked]"
                elif key == "thoughtSignature":
                    continue
                elif isinstance(value, dict):
                    result[key] = self._truncate_base64_in_response(value, max_length)
                elif isinstance(value, list):
                    result[key] = [self._truncate_base64_in_response(item, max_length) for item in value]
                else:
                    result[key] = value
            return result
        elif isinstance(data, list):
            return [self._truncate_base64_in_response(item, max_length) for item in data]
        else:
            return data

    def __str__(self):
        return f"{self.__class__.__name__}(driver_name={self.driver_name})"

    def __repr__(self):
        return self.__str__()
