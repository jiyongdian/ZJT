"""
常量注册表 - 通用反射提取器

自动从 config/constant.py 和 config/unified_config.py 中发现标记了
_CONSTANT_GROUP = True 的类，提取其成员及中文标签，供管理员常量参考页面使用。

新增常量类时，只需在类中添加 _CONSTANT_GROUP = True 和可选的 _LABELS 字典，
无需修改本文件。
"""
import inspect


def _serialize_value(value):
    """将值序列化为 JSON 兼容格式"""
    if isinstance(value, (tuple, frozenset)):
        return list(value)
    if isinstance(value, set):
        return sorted(list(value))
    return value


def _detect_type(value):
    """检测值的类型标识"""
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, (list, tuple, set, frozenset)):
        return 'collection'
    if isinstance(value, dict):
        return 'dict'
    return 'unknown'


def _extract_class_constants(cls):
    """从类中提取常量成员（跳过 _ 前缀、callable、方法等）"""
    labels = getattr(cls, '_LABELS', {})
    members = []
    for name, value in inspect.getmembers(cls):
        if name.startswith('_'):
            continue
        if callable(value) and not isinstance(value, (bool, int, float, str)):
            continue
        if isinstance(value, (classmethod, staticmethod, property)):
            continue

        members.append({
            'name': name,
            'value': _serialize_value(value),
            'type': _detect_type(value),
            'label': labels.get(name, ''),
        })

    def sort_key(m):
        v = m['value']
        if isinstance(v, (int, float)):
            return (0, v, '')
        if isinstance(v, str):
            return (1, 0, v)
        return (2, 0, str(v))

    members.sort(key=sort_key)
    return members


def _discover_groups():
    """自动发现两个配置模块中所有标记了 _CONSTANT_GROUP 的类"""
    import config.constant as const_mod
    import config.unified_config as unified_mod

    groups = [
        {
            'group_id': 'config_constant',
            'source': 'config/constant.py',
            'description': '系统基础常量',
            'module': const_mod,
        },
        {
            'group_id': 'config_unified',
            'source': 'config/unified_config.py',
            'description': '统一配置系统常量',
            'module': unified_mod,
        },
    ]
    return groups


def build_constants_response():
    """构建常量参考页面的完整响应数据"""
    from config.unified_config import IMPLEMENTATION_TO_ID

    result_groups = []
    for group_info in _discover_groups():
        module = group_info['module']
        classes_data = []

        # 自动发现模块中所有带 _CONSTANT_GROUP=True 的类
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not getattr(obj, '_CONSTANT_GROUP', False):
                continue
            # 确保类定义来自目标模块（排除导入的类）
            if obj.__module__ != module.__name__:
                continue

            members = _extract_class_constants(obj)
            classes_data.append({
                'class_name': name,
                'description': (obj.__doc__ or '').strip(),
                'member_count': len(members),
                'members': members,
            })

        # 按类名排序（保持稳定顺序）
        classes_data.sort(key=lambda c: c['class_name'])

        result_groups.append({
            'group_id': group_info['group_id'],
            'source': group_info['source'],
            'description': group_info['description'],
            'classes': classes_data,
        })

    # 构建 DriverImplementation <-> DriverImplementationId 映射表
    impl_mapping = []
    for impl_name, impl_id in sorted(IMPLEMENTATION_TO_ID.items(), key=lambda x: x[1]):
        impl_mapping.append({
            'name': impl_name,
            'id': impl_id,
            'label': '',
        })

    return {
        'groups': result_groups,
        'mappings': [
            {
                'mapping_name': 'DriverImplementation <-> ID',
                'description': '驱动实现名称与数据库存储ID的对应关系',
                'entries': impl_mapping,
            }
        ],
    }
