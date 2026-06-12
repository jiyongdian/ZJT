"""
constants_registry 常量注册表单元测试

测试 _serialize_value、_detect_type、_extract_class_constants、build_constants_response
等纯逻辑函数。
"""
import sys
import unittest
from unittest.mock import MagicMock

# Mock 数据库依赖（constants_registry 间接依赖）
_saved_db = sys.modules.get('model.database')
sys.modules['model.database'] = MagicMock()

from config.constants_registry import (
    _serialize_value,
    _detect_type,
    _extract_class_constants,
    build_constants_response,
)


class TestSerializeValue(unittest.TestCase):
    """测试 _serialize_value()"""

    def test_tuple_to_list(self):
        """tuple 转为 list"""
        self.assertEqual(_serialize_value((1, 2, 3)), [1, 2, 3])

    def test_frozenset_to_list(self):
        """frozenset 转为 list"""
        result = _serialize_value(frozenset([1, 2]))
        self.assertIsInstance(result, list)
        self.assertEqual(sorted(result), [1, 2])

    def test_set_to_sorted_list(self):
        """set 转为排序后的 list"""
        self.assertEqual(_serialize_value({3, 1, 2}), [1, 2, 3])

    def test_int_passthrough(self):
        """int 值不变"""
        self.assertEqual(_serialize_value(42), 42)

    def test_str_passthrough(self):
        """str 值不变"""
        self.assertEqual(_serialize_value("hello"), "hello")

    def test_bool_passthrough(self):
        """bool 值不变"""
        self.assertTrue(_serialize_value(True))

    def test_none_passthrough(self):
        """None 不变"""
        self.assertIsNone(_serialize_value(None))

    def test_float_passthrough(self):
        """float 值不变"""
        self.assertEqual(_serialize_value(3.14), 3.14)


class TestDetectType(unittest.TestCase):
    """测试 _detect_type()"""

    def test_bool(self):
        """bool 返回 'bool'"""
        self.assertEqual(_detect_type(True), 'bool')

    def test_int(self):
        """int 返回 'int'"""
        self.assertEqual(_detect_type(42), 'int')

    def test_float(self):
        """float 返回 'float'"""
        self.assertEqual(_detect_type(3.14), 'float')

    def test_string(self):
        """str 返回 'string'"""
        self.assertEqual(_detect_type("hello"), 'string')

    def test_list(self):
        """list 返回 'collection'"""
        self.assertEqual(_detect_type([1, 2, 3]), 'collection')

    def test_tuple(self):
        """tuple 返回 'collection'"""
        self.assertEqual(_detect_type((1, 2)), 'collection')

    def test_set(self):
        """set 返回 'collection'"""
        self.assertEqual(_detect_type({1, 2}), 'collection')

    def test_frozenset(self):
        """frozenset 返回 'collection'"""
        self.assertEqual(_detect_type(frozenset([1])), 'collection')

    def test_dict(self):
        """dict 返回 'dict'"""
        self.assertEqual(_detect_type({'a': 1}), 'dict')

    def test_none_returns_unknown(self):
        """None 返回 'unknown'"""
        self.assertEqual(_detect_type(None), 'unknown')


class TestExtractClassConstants(unittest.TestCase):
    """测试 _extract_class_constants()"""

    def test_extracts_public_constants(self):
        """提取公开常量"""
        class TestClass:
            A = 1
            B = "hello"
            _PRIVATE = "skip"

        members = _extract_class_constants(TestClass)
        names = [m['name'] for m in members]
        self.assertIn('A', names)
        self.assertIn('B', names)
        self.assertNotIn('_PRIVATE', names)

    def test_skips_methods(self):
        """跳过方法和 callable"""
        class TestClass:
            VALUE = 42
            def some_method(self):
                pass

        members = _extract_class_constants(TestClass)
        names = [m['name'] for m in members]
        self.assertIn('VALUE', names)
        self.assertNotIn('some_method', names)

    def test_labels_applied(self):
        """_LABELS 中的标签被正确应用"""
        class TestClass:
            STATUS_PENDING = 0
            STATUS_DONE = 1
            _LABELS = {'STATUS_PENDING': '待处理', 'STATUS_DONE': '已完成'}

        members = _extract_class_constants(TestClass)
        label_map = {m['name']: m['label'] for m in members}
        self.assertEqual(label_map['STATUS_PENDING'], '待处理')
        self.assertEqual(label_map['STATUS_DONE'], '已完成')

    def test_int_sorted_before_str(self):
        """int 类型排在 str 类型前面"""
        class TestClass:
            NAME = "abc"
            VALUE = 1

        members = _extract_class_constants(TestClass)
        self.assertEqual(members[0]['name'], 'VALUE')
        self.assertEqual(members[1]['name'], 'NAME')

    def test_numeric_sorted_by_value(self):
        """数值型按值排序"""
        class TestClass:
            C = 3
            A = 1
            B = 2

        members = _extract_class_constants(TestClass)
        values = [m['value'] for m in members]
        self.assertEqual(values, [1, 2, 3])

    def test_type_detection(self):
        """类型正确检测"""
        class TestClass:
            NUM = 1
            TEXT = "hello"
            FLAG = True

        members = _extract_class_constants(TestClass)
        type_map = {m['name']: m['type'] for m in members}
        self.assertEqual(type_map['NUM'], 'int')
        self.assertEqual(type_map['TEXT'], 'string')
        self.assertEqual(type_map['FLAG'], 'bool')

    def test_empty_class(self):
        """空类返回空列表"""
        class EmptyClass:
            pass

        members = _extract_class_constants(EmptyClass)
        self.assertEqual(members, [])

    def test_tuple_value_serialized(self):
        """tuple 值被序列化为 list"""
        class TestClass:
            ITEMS = (1, 2, 3)

        members = _extract_class_constants(TestClass)
        self.assertEqual(members[0]['value'], [1, 2, 3])
        self.assertEqual(members[0]['type'], 'collection')


class TestBuildConstantsResponse(unittest.TestCase):
    """测试 build_constants_response()"""

    def test_response_structure(self):
        """响应包含 groups 和 mappings"""
        result = build_constants_response()
        self.assertIn('groups', result)
        self.assertIn('mappings', result)

    def test_groups_is_list(self):
        """groups 是列表"""
        result = build_constants_response()
        self.assertIsInstance(result['groups'], list)
        self.assertGreater(len(result['groups']), 0)

    def test_group_has_required_keys(self):
        """每个 group 包含必要字段"""
        result = build_constants_response()
        for group in result['groups']:
            self.assertIn('group_id', group)
            self.assertIn('source', group)
            self.assertIn('description', group)
            self.assertIn('classes', group)

    def test_classes_sorted_by_name(self):
        """classes 按类名排序"""
        result = build_constants_response()
        for group in result['groups']:
            class_names = [c['class_name'] for c in group['classes']]
            self.assertEqual(class_names, sorted(class_names))

    def test_mappings_structure(self):
        """mappings 包含实现方映射"""
        result = build_constants_response()
        self.assertGreater(len(result['mappings']), 0)
        mapping = result['mappings'][0]
        self.assertIn('mapping_name', mapping)
        self.assertIn('entries', mapping)

    def test_impl_mapping_has_entries(self):
        """实现方映射有实际条目"""
        result = build_constants_response()
        impl_mapping = result['mappings'][0]
        self.assertGreater(len(impl_mapping['entries']), 0)
        for entry in impl_mapping['entries']:
            self.assertIn('name', entry)
            self.assertIn('id', entry)


# 恢复 sys.modules
if _saved_db is not None:
    sys.modules['model.database'] = _saved_db
else:
    sys.modules.pop('model.database', None)


if __name__ == '__main__':
    unittest.main()
