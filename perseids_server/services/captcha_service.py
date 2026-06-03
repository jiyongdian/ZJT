"""
CAPTCHA 验证服务 - 阿里云验证码2.0

提供人机验证功能，用于邮箱验证码发送前的安全校验。
使用阿里云 VerifyIntelligentCaptcha API 进行服务端验证。
"""

import logging
from typing import Dict, Any

from config.config_util import get_config_value

logger = logging.getLogger(__name__)


class CaptchaService:
    """阿里云 CAPTCHA 2.0 验证服务"""

    # 区域与 Endpoint 映射
    REGION_ENDPOINT_MAP = {
        'cn-shanghai': 'captcha.cn-shanghai.aliyuncs.com',
        'cn': 'captcha.cn-shanghai.aliyuncs.com',
        'sgp': 'captcha.ap-southeast-1.aliyuncs.com',
        'ap-southeast-1': 'captcha.ap-southeast-1.aliyuncs.com',
    }

    @staticmethod
    def is_enabled() -> bool:
        """检查 CAPTCHA 功能是否启用"""
        from config.config_util import get_dynamic_config_value
        return get_dynamic_config_value('captcha', 'enabled', default=False)

    @staticmethod
    def get_config() -> Dict[str, Any]:
        """获取 CAPTCHA 配置"""
        captcha_config = get_config_value('captcha', default={})
        aliyun_config = captcha_config.get('aliyun', {}) if isinstance(captcha_config, dict) else {}
        return {
            'enabled': CaptchaService.is_enabled(),
            'access_key_id': aliyun_config.get('access_key_id', ''),
            'access_key_secret': aliyun_config.get('access_key_secret', ''),
            'region_id': aliyun_config.get('region_id', 'cn-shanghai'),
            'prefix': aliyun_config.get('prefix', ''),
            'scene_id': aliyun_config.get('scene_id', ''),
        }

    @staticmethod
    def _get_endpoint(region_id: str) -> str:
        """根据区域获取 CAPTCHA 服务端点"""
        return CaptchaService.REGION_ENDPOINT_MAP.get(
            region_id, 'captcha.cn-shanghai.aliyuncs.com'
        )

    @staticmethod
    def verify_captcha(captcha_verify_param: str, scene_id: str = None) -> Dict[str, Any]:
        """
        验证阿里云 CAPTCHA

        Args:
            captcha_verify_param: 前端 CAPTCHA SDK 回调返回的验证参数（原样传递，禁止修改）
            scene_id: 场景ID，用于二次校验（可选，默认从配置读取）

        Returns:
            {"success": bool, "message": str, "verify_code": str}
        """
        try:
            config = CaptchaService.get_config()

            if not config['access_key_id'] or not config['access_key_secret']:
                logger.error("CAPTCHA 配置不完整：缺少 access_key_id 或 access_key_secret")
                return {
                    "success": False,
                    "message": "CAPTCHA 服务配置不完整",
                    "verify_code": ""
                }

            # 导入阿里云 SDK
            try:
                from alibabacloud_captcha20230305.client import Client as CaptchaClient
                from alibabacloud_captcha20230305 import models as captcha_models
                from alibabacloud_tea_openapi import models as open_api_models
                from alibabacloud_tea_util import models as util_models
            except ImportError as e:
                logger.error(f"阿里云 CAPTCHA SDK 未安装: {e}")
                return {
                    "success": False,
                    "message": "CAPTCHA SDK 未安装",
                    "verify_code": ""
                }

            # 初始化客户端
            api_config = open_api_models.Config(
                access_key_id=config['access_key_id'],
                access_key_secret=config['access_key_secret'],
            )
            api_config.endpoint = CaptchaService._get_endpoint(config['region_id'])
            client = CaptchaClient(api_config)

            # 构建验证请求
            request = captcha_models.VerifyIntelligentCaptchaRequest(
                captcha_verify_param=captcha_verify_param
            )

            # 如果提供了 scene_id，添加到请求中（防止前端被篡改）
            effective_scene_id = scene_id or config['scene_id']
            if effective_scene_id:
                request.scene_id = effective_scene_id

            # 调用阿里云验证接口（设置超时为 15 秒）
            runtime = util_models.RuntimeOptions(
                read_timeout=15000,
                connect_timeout=10000
            )
            response = client.verify_intelligent_captcha_with_options(request, runtime)

            # 解析结果
            result = response.body.result
            verify_result = result.verify_result if result else False
            verify_code = result.verify_code if result else ''

            logger.info(
                f"CAPTCHA 验证结果: verify_result={verify_result}, "
                f"verify_code={verify_code}"
            )

            if verify_result and verify_code in ('T001', 'T005'):
                return {
                    "success": True,
                    "message": "验证通过",
                    "verify_code": verify_code
                }
            else:
                logger.warning(
                    f"CAPTCHA 验证未通过: verify_code={verify_code}, "
                    f"verify_result={verify_result}"
                )
                return {
                    "success": False,
                    "message": f"人机验证未通过（{verify_code}）",
                    "verify_code": verify_code
                }

        except Exception as e:
            logger.error(f"CAPTCHA 验证异常: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"CAPTCHA 验证服务异常: {str(e)}",
                "verify_code": ""
            }
