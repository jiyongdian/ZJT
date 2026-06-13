"""
EmailDriverFactory、ApiEmailDriver、SmtpEmailDriver 单元测试

测试工厂创建逻辑、API 驱动发送逻辑、SMTP 驱动配置校验。
所有外部依赖（HTTP、SMTP、config）均使用 mock。
"""
import sys
import unittest
from unittest.mock import patch, MagicMock, Mock

# Mock 前置依赖
_saved_modules = {
    'config.config_util': sys.modules.get('config.config_util'),
    'model.database': sys.modules.get('model.database'),
}
sys.modules['config.config_util'] = MagicMock()
sys.modules['model.database'] = MagicMock()

from perseids_server.utils.email_drivers.api_email_driver import ApiEmailDriver
from perseids_server.utils.email_drivers.smtp_email_driver import SmtpEmailDriver
from perseids_server.utils.email_drivers.email_driver_factory import EmailDriverFactory

# 恢复
for _key, _orig in _saved_modules.items():
    if _orig is not None:
        sys.modules[_key] = _orig
    else:
        sys.modules.pop(_key, None)


# ==================== ApiEmailDriver 测试 ====================


class TestApiEmailDriverValidateConfig(unittest.TestCase):
    """测试 ApiEmailDriver.validate_config()"""

    def test_with_api_url_returns_true(self):
        """有 api_url 返回 True"""
        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        self.assertTrue(driver.validate_config())

    def test_without_api_url_returns_false(self):
        """无 api_url 返回 False"""
        driver = ApiEmailDriver({})
        self.assertFalse(driver.validate_config())

    def test_empty_api_url_returns_false(self):
        """空 api_url 返回 False"""
        driver = ApiEmailDriver({'api_url': ''})
        self.assertFalse(driver.validate_config())


class TestApiEmailDriverInit(unittest.TestCase):
    """测试 ApiEmailDriver 初始化"""

    def test_default_method_is_post(self):
        """默认 HTTP 方法为 POST"""
        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        self.assertEqual(driver.method, 'POST')

    def test_custom_method(self):
        """支持自定义 HTTP 方法"""
        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send', 'method': 'get'})
        self.assertEqual(driver.method, 'GET')

    def test_default_verify_ssl_true(self):
        """默认 verify_ssl 为 True"""
        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        self.assertTrue(driver.verify_ssl)

    def test_verify_ssl_false(self):
        """可配置 verify_ssl=False"""
        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send', 'verify_ssl': False})
        self.assertFalse(driver.verify_ssl)


class TestApiEmailDriverSendCode(unittest.TestCase):
    """测试 ApiEmailDriver.send_code()"""

    def test_missing_api_url_returns_failure(self):
        """配置不完整（无 api_url）返回失败"""
        driver = ApiEmailDriver({})
        result = driver.send_code('test@example.com', '123456')
        self.assertFalse(result['success'])
        self.assertIn('配置不完整', result['message'])

    @patch('perseids_server.utils.email_drivers.api_email_driver.httpx.Client')
    def test_post_success(self, MockClient):
        """POST 方式成功发送"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True, 'message': '发送成功'}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        result = driver.send_code('user@test.com', '654321')

        self.assertTrue(result['success'])
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        self.assertEqual(call_kwargs.kwargs['json'], {'email': 'user@test.com', 'code': '654321'})

    @patch('perseids_server.utils.email_drivers.api_email_driver.httpx.Client')
    def test_get_method(self, MockClient):
        """GET 方式发送请求参数在 params 中"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True, 'message': 'ok'}

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send', 'method': 'GET'})
        result = driver.send_code('user@test.com', '123456')

        self.assertTrue(result['success'])
        mock_client.get.assert_called_once()

    @patch('perseids_server.utils.email_drivers.api_email_driver.httpx.Client')
    def test_unsupported_method_returns_failure(self, MockClient):
        """不支持的 HTTP 方法返回失败"""
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send', 'method': 'DELETE'})
        result = driver.send_code('user@test.com', '123456')

        self.assertFalse(result['success'])
        self.assertIn('不支持', result['message'])

    @patch('perseids_server.utils.email_drivers.api_email_driver.httpx.Client')
    def test_400_status_returns_failure(self, MockClient):
        """HTTP 400 返回参数错误"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'success': False, 'message': '邮箱格式错误'}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        result = driver.send_code('invalid-email', '123456')

        self.assertFalse(result['success'])
        self.assertIn('邮箱格式错误', result['message'])

    @patch('perseids_server.utils.email_drivers.api_email_driver.httpx.Client')
    def test_429_rate_limit(self, MockClient):
        """HTTP 429 返回频率限制"""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {'success': False, 'message': '请求过于频繁'}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        result = driver.send_code('user@test.com', '123456')

        self.assertFalse(result['success'])
        self.assertIn('频繁', result['message'])

    @patch('perseids_server.utils.email_drivers.api_email_driver.httpx.Client')
    def test_500_server_error(self, MockClient):
        """HTTP 500 返回服务器错误"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {'success': False, 'message': '服务器内部错误'}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        result = driver.send_code('user@test.com', '123456')

        self.assertFalse(result['success'])

    @patch('perseids_server.utils.email_drivers.api_email_driver.httpx.Client')
    def test_timeout_returns_failure(self, MockClient):
        """超时返回失败"""
        import httpx
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        result = driver.send_code('user@test.com', '123456')

        self.assertFalse(result['success'])
        self.assertIn('超时', result['message'])

    @patch('perseids_server.utils.email_drivers.api_email_driver.httpx.Client')
    def test_api_returns_success_false(self, MockClient):
        """API 返回 success=False 时透传 message"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': False, 'message': '邮箱不存在'}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        result = driver.send_code('notexist@test.com', '123456')

        self.assertFalse(result['success'])
        self.assertIn('邮箱不存在', result['message'])

    @patch('perseids_server.utils.email_drivers.api_email_driver.httpx.Client')
    def test_invalid_json_response(self, MockClient):
        """API 返回非 JSON 格式时返回失败"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("invalid json")

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        driver = ApiEmailDriver({'api_url': 'https://mail.example.com/send'})
        result = driver.send_code('user@test.com', '123456')

        self.assertFalse(result['success'])
        self.assertIn('响应格式错误', result['message'])


# ==================== SmtpEmailDriver 测试 ====================


class TestSmtpEmailDriverValidateConfig(unittest.TestCase):
    """测试 SmtpEmailDriver.validate_config()"""

    def test_full_config_returns_true(self):
        """完整配置返回 True"""
        config = {
            'smtp_host': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_user': 'user@example.com',
            'smtp_password': 'password',
            'smtp_from': 'noreply@example.com',
        }
        driver = SmtpEmailDriver(config)
        self.assertTrue(driver.validate_config())

    def test_missing_smtp_host_returns_false(self):
        """缺少 smtp_host 返回 False"""
        config = {
            'smtp_user': 'user@example.com',
            'smtp_password': 'password',
            'smtp_from': 'noreply@example.com',
        }
        driver = SmtpEmailDriver(config)
        self.assertFalse(driver.validate_config())

    def test_missing_smtp_user_returns_false(self):
        """缺少 smtp_user 返回 False"""
        config = {
            'smtp_host': 'smtp.example.com',
            'smtp_password': 'password',
            'smtp_from': 'noreply@example.com',
        }
        driver = SmtpEmailDriver(config)
        self.assertFalse(driver.validate_config())

    def test_missing_smtp_from_returns_false(self):
        """缺少 smtp_from 返回 False"""
        config = {
            'smtp_host': 'smtp.example.com',
            'smtp_user': 'user@example.com',
            'smtp_password': 'password',
        }
        driver = SmtpEmailDriver(config)
        self.assertFalse(driver.validate_config())

    def test_default_port_is_587(self):
        """默认端口为 587"""
        driver = SmtpEmailDriver({'smtp_host': 'smtp.example.com'})
        self.assertEqual(driver.smtp_port, 587)

    def test_default_use_tls_true(self):
        """默认启用 TLS"""
        driver = SmtpEmailDriver({'smtp_host': 'smtp.example.com'})
        self.assertTrue(driver.use_tls)


# ==================== EmailDriverFactory 测试 ====================


class TestEmailDriverFactory(unittest.TestCase):
    """测试 EmailDriverFactory.get_driver()"""

    def setUp(self):
        """每个测试前重置单例"""
        EmailDriverFactory._instance = None
        EmailDriverFactory._current_agent = None

    def tearDown(self):
        EmailDriverFactory._instance = None
        EmailDriverFactory._current_agent = None

    @patch('perseids_server.utils.email_drivers.email_driver_factory.get_config_value')
    def test_no_active_driver_returns_none(self, mock_get_config):
        """未配置 active_driver 返回 None"""
        mock_get_config.return_value = {'agents': {}, 'active_driver': ''}
        driver = EmailDriverFactory.get_driver()
        self.assertIsNone(driver)

    @patch('perseids_server.utils.email_drivers.email_driver_factory.get_config_value')
    def test_unsupported_driver_type_returns_none(self, mock_get_config):
        """不支持的驱动类型返回 None"""
        mock_get_config.return_value = {
            'active_driver': 'wechat',
            'agents': {'agent1': {'driver': 'smtp'}}
        }
        driver = EmailDriverFactory.get_driver()
        self.assertIsNone(driver)

    @patch('perseids_server.utils.email_drivers.email_driver_factory.get_config_value')
    def test_no_matching_agent_returns_none(self, mock_get_config):
        """未找到匹配的 agent 配置返回 None"""
        mock_get_config.return_value = {
            'active_driver': 'api',
            'agents': {'agent1': {'driver': 'smtp'}}  # 只有 smtp agent，但 active 是 api
        }
        driver = EmailDriverFactory.get_driver()
        self.assertIsNone(driver)

    @patch('perseids_server.utils.email_drivers.email_driver_factory.get_config_value')
    def test_creates_api_driver(self, mock_get_config):
        """正确创建 ApiEmailDriver 实例"""
        mock_get_config.return_value = {
            'active_driver': 'api',
            'agents': {
                'api_agent': {
                    'driver': 'api',
                    'api_url': 'https://mail.example.com/send'
                }
            }
        }
        driver = EmailDriverFactory.get_driver()
        self.assertIsNotNone(driver)
        self.assertIsInstance(driver, ApiEmailDriver)

    @patch('perseids_server.utils.email_drivers.email_driver_factory.get_config_value')
    def test_creates_smtp_driver(self, mock_get_config):
        """正确创建 SmtpEmailDriver 实例"""
        mock_get_config.return_value = {
            'active_driver': 'smtp',
            'agents': {
                'smtp_agent': {
                    'driver': 'smtp',
                    'smtp_host': 'smtp.example.com',
                    'smtp_user': 'user@example.com',
                    'smtp_password': 'password',
                    'smtp_from': 'noreply@example.com',
                }
            }
        }
        driver = EmailDriverFactory.get_driver()
        self.assertIsNotNone(driver)
        self.assertIsInstance(driver, SmtpEmailDriver)

    @patch('perseids_server.utils.email_drivers.email_driver_factory.get_config_value')
    def test_singleton_pattern(self, mock_get_config):
        """单例模式：第二次调用返回同一实例"""
        mock_get_config.return_value = {
            'active_driver': 'api',
            'agents': {'api_agent': {'driver': 'api', 'api_url': 'https://mail.example.com/send'}}
        }
        driver1 = EmailDriverFactory.get_driver()
        driver2 = EmailDriverFactory.get_driver()
        self.assertIs(driver1, driver2)


class TestEmailDriverFactorySendCode(unittest.TestCase):
    """测试 EmailDriverFactory.send_code() 便捷方法"""

    def setUp(self):
        EmailDriverFactory._instance = None
        EmailDriverFactory._current_agent = None

    def tearDown(self):
        EmailDriverFactory._instance = None
        EmailDriverFactory._current_agent = None

    @patch('perseids_server.utils.email_drivers.email_driver_factory.EmailDriverFactory.get_driver')
    def test_no_driver_returns_failure(self, mock_get_driver):
        """无驱动时返回失败"""
        mock_get_driver.return_value = None
        result = EmailDriverFactory.send_code('test@example.com', '123456')
        self.assertFalse(result['success'])
        self.assertIn('未找到邮箱驱动', result['message'])

    @patch('perseids_server.utils.email_drivers.email_driver_factory.EmailDriverFactory.get_driver')
    def test_delegates_to_driver(self, mock_get_driver):
        """正确委托给驱动发送"""
        mock_driver = MagicMock()
        mock_driver.send_code.return_value = {'success': True, 'message': '发送成功'}
        mock_get_driver.return_value = mock_driver

        result = EmailDriverFactory.send_code('user@test.com', '654321')

        self.assertTrue(result['success'])
        mock_driver.send_code.assert_called_once_with('user@test.com', '654321')


if __name__ == '__main__':
    unittest.main()
