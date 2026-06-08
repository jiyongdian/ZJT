"""
VerifyCodeService 邮箱验证码服务单元测试

测试邮箱验证码创建、验证、生成等逻辑。
数据库操作和邮件发送均使用 mock。
"""
import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock 前置依赖
_saved_modules = {
    'model.database': sys.modules.get('model.database'),
    'config.config_util': sys.modules.get('config.config_util'),
}
sys.modules['model.database'] = MagicMock()
sys.modules['config.config_util'] = MagicMock()

from perseids_server.services.verify_code_service import VerifyCodeService

# 恢复
for _key, _orig in _saved_modules.items():
    if _orig is not None:
        sys.modules[_key] = _orig
    else:
        sys.modules.pop(_key, None)


class TestGenerateCode(unittest.TestCase):
    """测试 VerifyCodeService.generate_code()"""

    def test_default_length_6(self):
        """默认生成 6 位验证码"""
        code = VerifyCodeService.generate_code()
        self.assertEqual(len(code), 6)

    def test_all_digits(self):
        """生成的验证码全是数字"""
        code = VerifyCodeService.generate_code()
        self.assertTrue(code.isdigit())

    def test_custom_length(self):
        """支持自定义长度"""
        code = VerifyCodeService.generate_code(length=4)
        self.assertEqual(len(code), 4)
        self.assertTrue(code.isdigit())

    def test_randomness(self):
        """多次生成结果不完全相同（概率测试）"""
        codes = {VerifyCodeService.generate_code() for _ in range(20)}
        # 20 次生成至少应该有 2 种以上结果
        self.assertGreater(len(codes), 1)


class TestCreateEmailVerifyCode(unittest.TestCase):
    """测试 VerifyCodeService.create_email_verify_code()"""

    @patch('perseids_server.services.verify_code_service.EmailDriverFactory')
    @patch('perseids_server.services.verify_code_service.VerifyCodesModel')
    def test_valid_email_success(self, MockVerifyModel, MockEmailFactory):
        """有效邮箱创建成功并发送邮件"""
        MockEmailFactory.send_code.return_value = {'success': True, 'message': 'ok'}

        result = VerifyCodeService.create_email_verify_code('user@test.com', 'register')

        self.assertTrue(result['success'])
        self.assertIn('验证码已发送', result['message'])
        self.assertEqual(result['expire_minutes'], 5)
        MockVerifyModel.create_for_email.assert_called_once()
        MockEmailFactory.send_code.assert_called_once()

    def test_invalid_email_returns_failure(self):
        """无效邮箱格式返回失败"""
        result = VerifyCodeService.create_email_verify_code('not-an-email', 'register')
        self.assertFalse(result['success'])
        self.assertIn('无效的邮箱', result['message'])

    def test_invalid_type_returns_failure(self):
        """无效验证码类型返回失败"""
        result = VerifyCodeService.create_email_verify_code('user@test.com', 'invalid_type')
        self.assertFalse(result['success'])
        self.assertIn('无效的验证码类型', result['message'])

    @patch('perseids_server.services.verify_code_service.EmailDriverFactory')
    @patch('perseids_server.services.verify_code_service.VerifyCodesModel')
    def test_email_send_failure_returns_failure(self, MockVerifyModel, MockEmailFactory):
        """邮件发送失败时返回失败"""
        MockEmailFactory.send_code.return_value = {'success': False, 'message': '邮件服务异常'}

        result = VerifyCodeService.create_email_verify_code('user@test.com', 'register')

        self.assertFalse(result['success'])
        self.assertIn('邮件服务异常', result['message'])

    @patch('perseids_server.services.verify_code_service.VerifyCodesModel')
    def test_skip_send_email_for_testing(self, MockVerifyModel):
        """send_email=False 时跳过发送（用于测试）"""
        result = VerifyCodeService.create_email_verify_code(
            'user@test.com', 'register', send_email=False
        )

        self.assertTrue(result['success'])
        MockVerifyModel.create_for_email.assert_called_once()

    @patch('perseids_server.services.verify_code_service.EmailDriverFactory')
    @patch('perseids_server.services.verify_code_service.VerifyCodesModel')
    def test_login_type_valid(self, MockVerifyModel, MockEmailFactory):
        """login 类型有效"""
        MockEmailFactory.send_code.return_value = {'success': True, 'message': 'ok'}
        result = VerifyCodeService.create_email_verify_code('user@test.com', 'login')
        self.assertTrue(result['success'])

    @patch('perseids_server.services.verify_code_service.EmailDriverFactory')
    @patch('perseids_server.services.verify_code_service.VerifyCodesModel')
    def test_reset_password_type_valid(self, MockVerifyModel, MockEmailFactory):
        """reset_password 类型有效"""
        MockEmailFactory.send_code.return_value = {'success': True, 'message': 'ok'}
        result = VerifyCodeService.create_email_verify_code('user@test.com', 'reset_password')
        self.assertTrue(result['success'])


class TestVerifyEmailCode(unittest.TestCase):
    """测试 VerifyCodeService.verify_email_code()"""

    @patch('perseids_server.services.verify_code_service.VerifyCodesModel')
    def test_valid_code_success(self, MockVerifyModel):
        """正确验证码返回成功"""
        MockVerifyModel.verify_for_email.return_value = True

        result = VerifyCodeService.verify_email_code('user@test.com', '123456', 'register')

        self.assertTrue(result['success'])
        self.assertIn('验证成功', result['message'])
        MockVerifyModel.mark_used_for_email.assert_called_once_with(
            'user@test.com', '123456', 'register'
        )

    @patch('perseids_server.services.verify_code_service.VerifyCodesModel')
    def test_wrong_code_returns_failure(self, MockVerifyModel):
        """错误验证码返回失败"""
        MockVerifyModel.verify_for_email.return_value = False

        result = VerifyCodeService.verify_email_code('user@test.com', '000000', 'register')

        self.assertFalse(result['success'])
        self.assertIn('不正确或已过期', result['message'])
        MockVerifyModel.mark_used_for_email.assert_not_called()

    def test_invalid_email_returns_failure(self):
        """无效邮箱格式返回失败"""
        result = VerifyCodeService.verify_email_code('not-an-email', '123456', 'register')
        self.assertFalse(result['success'])
        self.assertIn('无效的邮箱', result['message'])

    def test_invalid_type_returns_failure(self):
        """无效验证码类型返回失败"""
        result = VerifyCodeService.verify_email_code('user@test.com', '123456', 'invalid_type')
        self.assertFalse(result['success'])
        self.assertIn('无效的验证码类型', result['message'])


class TestCreateSmsVerifyCode(unittest.TestCase):
    """测试 VerifyCodeService.create_verify_code() 短信验证码"""

    def test_invalid_phone_returns_failure(self):
        """无效手机号返回失败"""
        result = VerifyCodeService.create_verify_code('123', 'register')
        self.assertFalse(result['success'])
        self.assertIn('无效的手机号', result['message'])

    def test_invalid_type_returns_failure(self):
        """无效类型返回失败"""
        result = VerifyCodeService.create_verify_code('13800138000', 'invalid_type')
        self.assertFalse(result['success'])
        self.assertIn('无效的验证码类型', result['message'])


class TestVerifySmsCode(unittest.TestCase):
    """测试 VerifyCodeService.verify_code() 短信验证码验证"""

    def test_invalid_phone_returns_failure(self):
        """无效手机号返回失败"""
        result = VerifyCodeService.verify_code('123', '123456', 'register')
        self.assertFalse(result['success'])

    def test_invalid_type_returns_failure(self):
        """无效类型返回失败"""
        result = VerifyCodeService.verify_code('13800138000', '123456', 'invalid_type')
        self.assertFalse(result['success'])


class TestValidTypesConstant(unittest.TestCase):
    """测试 VALID_TYPES 常量"""

    def test_valid_types_contains_expected(self):
        """VALID_TYPES 包含预期的类型"""
        self.assertIn('register', VerifyCodeService.VALID_TYPES)
        self.assertIn('login', VerifyCodeService.VALID_TYPES)
        self.assertIn('reset_password', VerifyCodeService.VALID_TYPES)

    def test_code_length_is_6(self):
        """CODE_LENGTH 为 6"""
        self.assertEqual(VerifyCodeService.CODE_LENGTH, 6)

    def test_expire_minutes_is_5(self):
        """CODE_EXPIRE_MINUTES 为 5"""
        self.assertEqual(VerifyCodeService.CODE_EXPIRE_MINUTES, 5)


if __name__ == '__main__':
    unittest.main()
