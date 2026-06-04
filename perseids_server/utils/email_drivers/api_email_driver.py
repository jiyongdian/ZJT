"""
基于HTTP API的邮箱发送驱动

通过调用外部HTTP API发送验证码邮件，无需本地配置SMTP。
适用于将邮件发送能力委托给远程邮件服务的场景。
"""
import logging
import httpx
from typing import Dict

from .base_email_driver import BaseEmailDriver

logger = logging.getLogger(__name__)


class ApiEmailDriver(BaseEmailDriver):
    """基于HTTP API的邮箱发送驱动"""

    def __init__(self, config: Dict):
        """
        初始化API邮件驱动

        Args:
            config: 配置字典，应包含:
                - api_url: 邮件API接口地址（必需）
                - method: 请求方法（可选，默认POST）
                - verify_ssl: 是否验证SSL证书（可选，默认True）
        """
        super().__init__(config)
        self.api_url = config.get('api_url')
        self.method = config.get('method', 'POST').upper()
        self.verify_ssl = config.get('verify_ssl', True)

    def validate_config(self) -> bool:
        """验证配置是否完整"""
        return bool(self.api_url)

    def send_code(self, email: str, code: str) -> Dict[str, any]:
        """
        通过HTTP API发送验证码邮件

        向外部邮件API发送请求，请求体包含 email 和 code 字段。
        API响应格式需遵循:
            {"success": bool, "message": str}

        Args:
            email: 收件邮箱地址
            code: 验证码

        Returns:
            {"success": bool, "message": str}
        """
        try:
            if not self.validate_config():
                logger.error("API邮件配置不完整：缺少api_url")
                return {"success": False, "message": "邮件服务配置不完整"}

            # 构建请求参数
            params = {
                "email": email,
                "code": code
            }

            # 发送HTTP请求
            # 显式使用 HTTP/1.1 避免 macOS 上的 SSL EOF 问题
            with httpx.Client(timeout=15, http2=False, verify=self.verify_ssl) as client:
                if self.method == 'POST':
                    response = client.post(
                        self.api_url,
                        json=params
                    )
                elif self.method == 'GET':
                    response = client.get(
                        self.api_url,
                        params=params
                    )
                else:
                    logger.error(f"不支持的HTTP方法: {self.method}")
                    return {"success": False, "message": f"不支持的HTTP方法: {self.method}"}

            # 解析响应
            try:
                result = response.json()
            except Exception:
                logger.error(f"API响应格式错误，状态码: {response.status_code}")
                return {"success": False, "message": "邮件API响应格式错误"}

            # 根据HTTP状态码处理响应
            if response.status_code == 200:
                success = result.get('success', False)
                message = result.get('message', '验证码邮件发送成功')

                if success:
                    logger.info(f"邮件发送成功: {email}")
                    return {"success": True, "message": message}
                else:
                    logger.error(f"邮件发送失败: {message}")
                    return {"success": False, "message": message}

            elif response.status_code == 400:
                message = result.get('message', '请求参数错误')
                logger.error(f"请求参数错误: {message}")
                return {"success": False, "message": message}

            elif response.status_code == 429:
                message = result.get('message', '请求过于频繁，请稍后再试')
                logger.warning(f"请求频率限制: {message}")
                return {"success": False, "message": message}

            elif response.status_code == 500:
                message = result.get('message', '服务器内部错误')
                logger.error(f"邮件API服务器错误: {message}")
                return {"success": False, "message": message}

            else:
                message = result.get('message', f'未知错误 (HTTP {response.status_code})')
                logger.error(f"邮件发送失败: {message}")
                return {"success": False, "message": message}

        except httpx.TimeoutException:
            logger.error(f"邮件发送超时: {self.api_url}")
            return {"success": False, "message": "邮件发送超时"}
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
            return {"success": False, "message": f"发送邮件失败: {str(e)}"}
