"""
SOP 加载器单元测试

测试 SopLoader 的纯函数逻辑：front matter 解析、索引构建、内容加载。
不依赖真实文件系统，使用临时目录。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from agents.skill_loader import SopLoader


class TestParseFrontMatter(unittest.TestCase):
    """测试 _parse_front_matter 方法"""

    def _create_sop_file(self, sop_dir: Path, name: str, content: str) -> Path:
        file_path = sop_dir / f"{name}.md"
        # 强制使用 \n 换行符，避免 Windows \r\n 导致正则匹配失败
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        return file_path

    def test_valid_front_matter(self):
        """测试正常 front matter 解析"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            content = """---
name: test-sop
description: 这是一个测试 SOP
author: test
---
# 正文内容
这是 SOP 的正文。
"""
            file_path = self._create_sop_file(sop_dir, "test", content)
            loader = SopLoader(str(sop_dir))
            result = loader._parse_front_matter(file_path)
            self.assertEqual(result['name'], 'test-sop')
            self.assertEqual(result['description'], '这是一个测试 SOP')
            self.assertEqual(result['author'], 'test')

    def test_no_front_matter(self):
        """测试没有 front matter 的文件"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            content = "# 没有 front matter\n正文"
            file_path = self._create_sop_file(sop_dir, "no_fm", content)
            loader = SopLoader(str(sop_dir))
            result = loader._parse_front_matter(file_path)
            self.assertIsNone(result)

    def test_empty_front_matter(self):
        """测试空的 front matter（正则不匹配，返回 None）"""
        from unittest.mock import patch
        loader = SopLoader("/tmp")
        with patch.object(Path, 'read_text', return_value="---\n---\n正文"):
            result = loader._parse_front_matter(Path("fake.md"))
        self.assertIsNone(result)

    def test_multiline_description(self):
        """测试多行 description（当前实现只按第一行解析）"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            content = """---
name: multi-line
description: 第一行
extra: value
---
正文"""
            file_path = self._create_sop_file(sop_dir, "multi", content)
            loader = SopLoader(str(sop_dir))
            result = loader._parse_front_matter(file_path)
            # 注意：当前实现按行 split，多行 description 会被截断
            self.assertEqual(result['description'], '第一行')

    def test_special_chars_in_value(self):
        """测试值中包含冒号的情况"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            content = """---
name: test
url: http://example.com:8080/path
---
正文"""
            file_path = self._create_sop_file(sop_dir, "special", content)
            loader = SopLoader(str(sop_dir))
            result = loader._parse_front_matter(file_path)
            # line.split(':', 1) 只分割一次，所以值保留完整
            self.assertEqual(result['url'], 'http://example.com:8080/path')

    def test_file_not_found(self):
        """测试文件不存在时返回 None"""
        with tempfile.TemporaryDirectory() as tmp:
            loader = SopLoader(str(tmp))
            result = loader._parse_front_matter(Path(tmp) / "nonexistent.md")
            self.assertIsNone(result)


class TestBuildSopsIndex(unittest.TestCase):
    """测试 build_sops_index 方法"""

    def test_empty_metadata(self):
        """测试空 metadata 返回空字符串"""
        with tempfile.TemporaryDirectory() as tmp:
            loader = SopLoader(str(tmp))
            result = loader.build_sops_index()
            self.assertEqual(result, "")

    def test_single_sop(self):
        """测试单个 SOP 索引"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            with open(sop_dir / "sop1.md", 'w', encoding='utf-8', newline='\n') as f:
                f.write("""---
name: sop-1
description: 描述一
---
正文""")
            loader = SopLoader(str(sop_dir))
            result = loader.build_sops_index()
            self.assertIn("| SOP 名称 | 描述 |", result)
            self.assertIn("| sop-1 | 描述一 |", result)

    def test_multiple_sops_sorted(self):
        """测试多个 SOP 按名称排序"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            with open(sop_dir / "b.md", 'w', encoding='utf-8', newline='\n') as f:
                f.write("""---
name: beta
description: B描述
---
正文""")
            with open(sop_dir / "a.md", 'w', encoding='utf-8', newline='\n') as f:
                f.write("""---
name: alpha
description: A描述
---
正文""")
            loader = SopLoader(str(sop_dir))
            result = loader.build_sops_index()
            lines = result.split('\n')
            # 按名称排序后 alpha 应在 beta 前面
            self.assertTrue(lines[2].startswith("| alpha"))
            self.assertTrue(lines[3].startswith("| beta"))

    def test_no_description(self):
        """测试没有 description 时显示空字符串（metadata 中默认空字符串）"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            with open(sop_dir / "sop.md", 'w', encoding='utf-8', newline='\n') as f:
                f.write("""---
name: no-desc
---
正文""")
            loader = SopLoader(str(sop_dir))
            result = loader.build_sops_index()
            # _load_all_sops_metadata 中 description 默认 ''，build_sops_index 中 meta.get('description', '无描述') 拿到 ''
            self.assertIn("| no-desc |  |", result)


class TestLoadSkillWithIndex(unittest.TestCase):
    """测试 load_skill_with_index 方法"""

    def test_replace_placeholder(self):
        """测试 {{SOP_INDEX}} 占位符替换"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            (sop_dir / "sop.md").write_text("""---
name: my-sop
description: 我的SOP
---
正文""", encoding='utf-8')
            loader = SopLoader(str(sop_dir))
            skill_content = "系统提示\n\n{{SOP_INDEX}}\n\n结束"
            result = loader.load_skill_with_index(skill_content)
            self.assertNotIn("{{SOP_INDEX}}", result)
            self.assertIn("| my-sop | 我的SOP |", result)
            self.assertIn("系统提示", result)
            self.assertIn("结束", result)

    def test_no_placeholder(self):
        """测试没有占位符时不改变内容"""
        with tempfile.TemporaryDirectory() as tmp:
            loader = SopLoader(str(tmp))
            skill_content = "没有占位符的内容"
            result = loader.load_skill_with_index(skill_content)
            self.assertEqual(result, skill_content)


class TestGetSopContent(unittest.TestCase):
    """测试 get_sop_content 方法"""

    def test_get_content_without_front_matter(self):
        """测试获取去掉 front matter 后的正文"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            (sop_dir / "sop.md").write_text("""---
name: test-sop
---
# 标题
正文内容
第二行
""", encoding='utf-8')
            loader = SopLoader(str(sop_dir))
            content = loader.get_sop_content("test-sop")
            self.assertEqual(content, "# 标题\n正文内容\n第二行")

    def test_content_without_front_matter(self):
        """测试没有 front matter 时返回全部内容"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            (sop_dir / "sop.md").write_text("# 直接正文\n内容", encoding='utf-8')
            loader = SopLoader(str(sop_dir))
            # 由于没有 front matter，_parse_front_matter 返回 None，所以不会被加入 metadata
            # 需要手动加入 metadata 来测试 get_sop_content
            loader.sops_metadata["direct"] = {"name": "direct", "file": str(sop_dir / "sop.md")}
            content = loader.get_sop_content("direct")
            self.assertEqual(content, "# 直接正文\n内容")

    def test_missing_sop(self):
        """测试不存在的 SOP 返回 None"""
        with tempfile.TemporaryDirectory() as tmp:
            loader = SopLoader(str(tmp))
            content = loader.get_sop_content("nonexistent")
            self.assertIsNone(content)


class TestSopsConfig(unittest.TestCase):
    """测试 sops_config.json 加载"""

    def test_load_tools_config(self):
        """测试从 sops_config.json 读取工具列表"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            (sop_dir / "sops_config.json").write_text(
                '{"sop-1": {"allowed_tools": ["tool_a", "tool_b"]}}',
                encoding='utf-8'
            )
            (sop_dir / "sop.md").write_text("""---
name: sop-1
description: 测试
---
正文""", encoding='utf-8')
            loader = SopLoader(str(sop_dir))
            tools = loader.get_sop_tools("sop-1")
            self.assertEqual(tools, ["tool_a", "tool_b"])

    def test_missing_config(self):
        """测试 sops_config.json 不存在时返回空"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            loader = SopLoader(str(sop_dir))
            tools = loader.get_sop_tools("any")
            self.assertEqual(tools, [])

    def test_missing_sop_in_config(self):
        """测试 SOP 在 config 中不存在时返回空"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            (sop_dir / "sops_config.json").write_text('{}', encoding='utf-8')
            (sop_dir / "sop.md").write_text("""---
name: sop-1
---
正文""", encoding='utf-8')
            loader = SopLoader(str(sop_dir))
            tools = loader.get_sop_tools("sop-1")
            self.assertEqual(tools, [])

    def test_malformed_config(self):
        """测试损坏的 JSON 返回空"""
        with tempfile.TemporaryDirectory() as tmp:
            sop_dir = Path(tmp)
            (sop_dir / "sops_config.json").write_text('not json', encoding='utf-8')
            loader = SopLoader(str(sop_dir))
            tools = loader.get_sop_tools("any")
            self.assertEqual(tools, [])


if __name__ == '__main__':
    unittest.main()
