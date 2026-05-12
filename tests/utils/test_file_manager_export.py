"""
文件管理器导出/导入功能单元测试

测试 FileManager 新增的 export_world / import_world 及相关辅助方法。
不依赖数据库，使用临时目录模拟文件系统。
"""
import os
import sys
import json
import shutil
import tempfile
import zipfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from script_writer_core.file_manager import FileManager


class TestCollectImageFromUrl(unittest.TestCase):
    """测试 _collect_image_from_url 方法"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_fm_collect_")
        self.fm = FileManager(base_dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_upload_file(self, image_type: str, filename: str) -> Path:
        """在 upload 目录创建一个假图片文件"""
        file_path = Path(self.tmp_dir) / "upload" / image_type / "pic" / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b'\x89PNG\r\n\x1a\n')  # PNG magic bytes
        return file_path

    def test_valid_character_url(self):
        """测试解析角色图片 URL"""
        self._create_upload_file("character", "abc-123.png")
        url = "http://localhost:9003/upload/character/pic/abc-123.png"
        result = self.fm._collect_image_from_url(url)
        self.assertIsNotNone(result)
        image_type, filename, file_path = result
        self.assertEqual(image_type, "character")
        self.assertEqual(filename, "abc-123.png")
        self.assertTrue(file_path.exists())

    def test_valid_location_url(self):
        """测试解析场景图片 URL"""
        self._create_upload_file("location", "loc-456.jpg")
        url = "http://example.com/upload/location/pic/loc-456.jpg"
        result = self.fm._collect_image_from_url(url)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "location")
        self.assertEqual(result[1], "loc-456.jpg")

    def test_valid_props_url(self):
        """测试解析道具图片 URL"""
        self._create_upload_file("props", "prop-789.webp")
        url = "https://cdn.example.com/upload/props/pic/prop-789.webp"
        result = self.fm._collect_image_from_url(url)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "props")
        self.assertEqual(result[1], "prop-789.webp")

    def test_file_not_exists(self):
        """测试文件不存在时返回 None"""
        url = "http://localhost:9003/upload/character/pic/nonexistent.png"
        result = self.fm._collect_image_from_url(url)
        self.assertIsNone(result)

    def test_invalid_url_no_match(self):
        """测试不匹配的 URL 返回 None"""
        result = self.fm._collect_image_from_url("http://example.com/other/path.png")
        self.assertIsNone(result)

    def test_empty_url(self):
        """测试空 URL 返回 None"""
        self.assertIsNone(self.fm._collect_image_from_url(""))
        self.assertIsNone(self.fm._collect_image_from_url(None))

    def test_url_with_query_params(self):
        """测试带查询参数的 URL（文件名包含查询参数，文件不存在返回 None）"""
        # 当前正则会将查询参数作为 filename 的一部分
        # 文件系统上不存在 "test.png?width=100"，所以返回 None
        self._create_upload_file("character", "test.png")
        url = "http://localhost:9003/upload/character/pic/test.png?width=100"
        result = self.fm._collect_image_from_url(url)
        # 文件名包含查询参数，实际文件不存在
        self.assertIsNone(result)


class TestRewriteImageUrls(unittest.TestCase):
    """测试 _rewrite_image_urls 方法"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_fm_rewrite_")
        self.fm = FileManager(base_dir=self.tmp_dir)
        self.image_mapping = {}
        self.collected = set()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_upload_file(self, image_type: str, filename: str) -> Path:
        file_path = Path(self.tmp_dir) / "upload" / image_type / "pic" / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b'\x89PNG\r\n\x1a\n')
        return file_path

    def test_rewrite_single_reference_image(self):
        """测试替换单张 reference_image（无 zipf 时 collected 不更新）"""
        self._create_upload_file("character", "char-001.png")
        data = {
            "name": "角色A",
            "reference_image": "http://localhost:9003/upload/character/pic/char-001.png"
        }
        result = self.fm._rewrite_image_urls(data, self.image_mapping, self.collected)
        self.assertEqual(result["reference_image"], "images/char-001.png")
        # collected 只在 zipf 存在时更新
        self.assertEqual(len(self.collected), 0)
        self.assertIn("char-001.png", self.image_mapping)

    def test_rewrite_reference_images_list(self):
        """测试替换多角度参考图列表"""
        self._create_upload_file("location", "loc-001.png")
        self._create_upload_file("location", "loc-002.png")
        data = {
            "name": "场景A",
            "reference_images": [
                {"url": "http://localhost:9003/upload/location/pic/loc-001.png", "angle": "front"},
                {"url": "http://localhost:9003/upload/location/pic/loc-002.png", "angle": "side"},
            ]
        }
        result = self.fm._rewrite_image_urls(data, self.image_mapping, self.collected)
        self.assertEqual(result["reference_images"][0]["url"], "images/loc-001.png")
        self.assertEqual(result["reference_images"][1]["url"], "images/loc-002.png")
        self.assertEqual(result["reference_images"][0]["angle"], "front")
        # collected 只在 zipf 存在时更新
        self.assertEqual(len(self.collected), 0)
        self.assertEqual(len(self.image_mapping), 2)

    def test_no_image_fields(self):
        """测试没有图片字段的数据"""
        data = {"name": "测试", "description": "无图片"}
        result = self.fm._rewrite_image_urls(data, self.image_mapping, self.collected)
        self.assertEqual(result, data)
        self.assertEqual(len(self.collected), 0)

    def test_nested_dict(self):
        """测试嵌套字典"""
        self._create_upload_file("props", "prop-001.png")
        data = {
            "character": {
                "name": "角色",
                "reference_image": "http://localhost:9003/upload/props/pic/prop-001.png"
            }
        }
        result = self.fm._rewrite_image_urls(data, self.image_mapping, self.collected)
        self.assertEqual(result["character"]["reference_image"], "images/prop-001.png")

    def test_list_of_dicts(self):
        """测试字典列表"""
        self._create_upload_file("character", "c1.png")
        self._create_upload_file("character", "c2.png")
        data = [
            {"name": "角色1", "reference_image": "http://localhost:9003/upload/character/pic/c1.png"},
            {"name": "角色2", "reference_image": "http://localhost:9003/upload/character/pic/c2.png"},
        ]
        result = self.fm._rewrite_image_urls(data, self.image_mapping, self.collected)
        self.assertEqual(result[0]["reference_image"], "images/c1.png")
        self.assertEqual(result[1]["reference_image"], "images/c2.png")

    def test_deduplicate_images(self):
        """测试重复图片在 image_mapping 中只记录一次"""
        self._create_upload_file("character", "same.png")
        # _rewrite_image_urls 只处理 reference_image 和 reference_images 这两个 key
        data = {
            "char1": {"reference_image": "http://localhost:9003/upload/character/pic/same.png"},
            "char2": {"reference_image": "http://localhost:9003/upload/character/pic/same.png"},
        }
        result = self.fm._rewrite_image_urls(data, self.image_mapping, self.collected)
        # image_mapping 中只有一条记录（同一张图片）
        self.assertEqual(len(self.image_mapping), 1)
        self.assertIn("same.png", self.image_mapping)

    def test_empty_reference_image_string(self):
        """测试空字符串 reference_image 不处理"""
        data = {"reference_image": ""}
        result = self.fm._rewrite_image_urls(data, self.image_mapping, self.collected)
        self.assertEqual(result["reference_image"], "")

    def test_with_zipfile(self):
        """测试写入 zip 文件"""
        self._create_upload_file("character", "zip-test.png")
        zip_path = Path(self.tmp_dir) / "test.zip"
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            data = {"reference_image": "http://localhost:9003/upload/character/pic/zip-test.png"}
            self.fm._rewrite_image_urls(data, self.image_mapping, self.collected, zipf)

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            self.assertIn("images/zip-test.png", zipf.namelist())


class TestRestoreImageUrls(unittest.TestCase):
    """测试 _restore_image_urls 方法"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_fm_restore_")
        self.fm = FileManager(base_dir=self.tmp_dir)
        self.upload_base = Path(self.tmp_dir) / "upload"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_restore_single_reference_image(self):
        """测试还原单张 reference_image"""
        reverse_mapping = {"char-001.png": "/upload/character/pic/char-001.png"}
        uploaded = {}
        data = {"reference_image": "images/char-001.png"}
        result = self.fm._restore_image_urls(data, reverse_mapping, uploaded, self.upload_base)
        self.assertEqual(result["reference_image"], "/upload/character/pic/char-001.png")
        self.assertIn("char-001.png", uploaded)

    def test_restore_reference_images_list(self):
        """测试还原多角度参考图列表"""
        reverse_mapping = {
            "loc-001.png": "/upload/location/pic/loc-001.png",
            "loc-002.png": "/upload/location/pic/loc-002.png",
        }
        uploaded = {}
        data = {
            "reference_images": [
                {"url": "images/loc-001.png", "angle": "front"},
                {"url": "images/loc-002.png", "angle": "side"},
            ]
        }
        result = self.fm._restore_image_urls(data, reverse_mapping, uploaded, self.upload_base)
        self.assertEqual(result["reference_images"][0]["url"], "/upload/location/pic/loc-001.png")
        self.assertEqual(result["reference_images"][1]["url"], "/upload/location/pic/loc-002.png")
        self.assertEqual(result["reference_images"][0]["angle"], "front")

    def test_no_image_fields(self):
        """测试没有图片字段的数据"""
        reverse_mapping = {}
        uploaded = {}
        data = {"name": "测试", "description": "无图片"}
        result = self.fm._restore_image_urls(data, reverse_mapping, uploaded, self.upload_base)
        self.assertEqual(result, data)

    def test_nested_dict(self):
        """测试嵌套字典"""
        reverse_mapping = {"prop.png": "/upload/props/pic/prop.png"}
        uploaded = {}
        data = {"item": {"reference_image": "images/prop.png"}}
        result = self.fm._restore_image_urls(data, reverse_mapping, uploaded, self.upload_base)
        self.assertEqual(result["item"]["reference_image"], "/upload/props/pic/prop.png")

    def test_image_not_in_mapping(self):
        """测试图片不在映射中时保持原值"""
        reverse_mapping = {}
        uploaded = {}
        data = {"reference_image": "images/unknown.png"}
        result = self.fm._restore_image_urls(data, reverse_mapping, uploaded, self.upload_base)
        self.assertEqual(result["reference_image"], "images/unknown.png")


class TestExportWorld(unittest.TestCase):
    """测试 export_world 方法"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_fm_export_")
        self.fm = FileManager(base_dir=self.tmp_dir)
        self.user_id = "test_user"
        self.world_id = "test_world"
        # 创建世界目录结构
        self.fm._ensure_directories(self.user_id, self.world_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_character_json(self, name: str, image_url: str = None) -> Path:
        """创建角色 JSON 文件"""
        base_path = self.fm._get_user_world_path(self.user_id, self.world_id)
        char_dir = base_path / "characters"
        char_dir.mkdir(parents=True, exist_ok=True)
        data = {"name": name}
        if image_url:
            data["reference_image"] = image_url
        file_path = char_dir / f"{name}.json"
        file_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return file_path

    def test_export_basic(self):
        """测试基本导出功能"""
        self._create_character_json("角色A")
        zip_path = self.fm.export_world(self.user_id, self.world_id)
        self.assertTrue(os.path.exists(zip_path))
        self.assertTrue(zip_path.endswith('.zip'))

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            names = zipf.namelist()
            self.assertIn("metadata.json", names)
            self.assertIn("characters/角色A.json", names)
            # 验证 metadata
            metadata = json.loads(zipf.read("metadata.json"))
            self.assertEqual(metadata["world_id"], self.world_id)
            self.assertEqual(metadata["user_id"], self.user_id)
            self.assertEqual(metadata["export_version"], "1.0")

        os.unlink(zip_path)

    def test_export_with_images(self):
        """测试导出包含图片"""
        # 创建图片文件
        base_path = self.fm._get_user_world_path(self.user_id, self.world_id)
        img_dir = Path(self.tmp_dir) / "upload" / "character" / "pic"
        img_dir.mkdir(parents=True, exist_ok=True)
        img_file = img_dir / "char-img.png"
        img_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)

        # 创建角色引用该图片
        self._create_character_json("有图角色", f"http://localhost:9003/upload/character/pic/char-img.png")

        zip_path = self.fm.export_world(self.user_id, self.world_id)

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            names = zipf.namelist()
            self.assertIn("images/char-img.png", names)
            self.assertIn("image_mapping.json", names)
            # 验证 image_mapping
            mapping = json.loads(zipf.read("image_mapping.json"))
            self.assertIn("char-img.png", mapping)
            # 验证 metadata 中的图片计数
            metadata = json.loads(zipf.read("metadata.json"))
            self.assertEqual(metadata["image_count"], 1)

        os.unlink(zip_path)

    def test_export_with_script_problem(self):
        """测试导出包含 script_problem.json"""
        base_path = self.fm._get_user_world_path(self.user_id, self.world_id)
        problem_file = base_path / "script_problem.json"
        problem_data = {"verdict": False, "problem": "测试问题"}
        problem_file.write_text(json.dumps(problem_data), encoding='utf-8')

        zip_path = self.fm.export_world(self.user_id, self.world_id)

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            self.assertIn("script_problem.json", zipf.namelist())
            content = json.loads(zipf.read("script_problem.json"))
            self.assertEqual(content["problem"], "测试问题")

        os.unlink(zip_path)

    def test_export_world_not_found(self):
        """测试导出不存在的世界"""
        with self.assertRaises(FileNotFoundError):
            self.fm.export_world("nonexistent_user", "nonexistent_world")


class TestImportWorld(unittest.TestCase):
    """测试 import_world 方法"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_fm_import_")
        self.fm = FileManager(base_dir=self.tmp_dir)
        self.user_id = "import_user"
        self.world_id = "import_world"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_export_zip(self, characters=None, locations=None, images=None, script_problem=None) -> str:
        """创建一个模拟的导出 zip 文件"""
        zip_path = os.path.join(self.tmp_dir, "test_export.zip")
        image_mapping = {}

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加角色
            if characters:
                for char in characters:
                    zipf.writestr(f"characters/{char['name']}.json", json.dumps(char, ensure_ascii=False))

            # 添加场景
            if locations:
                for loc in locations:
                    zipf.writestr(f"locations/{loc['name']}.json", json.dumps(loc, ensure_ascii=False))

            # 添加图片
            if images:
                for img_name, img_data in images.items():
                    zipf.writestr(f"images/{img_name}", img_data)
                    image_mapping[img_name] = f"/upload/character/pic/{img_name}"

            # 添加 image_mapping
            if image_mapping:
                zipf.writestr("image_mapping.json", json.dumps(image_mapping, ensure_ascii=False))

            # 添加 script_problem
            if script_problem:
                zipf.writestr("script_problem.json", json.dumps(script_problem, ensure_ascii=False))

            # 添加 metadata
            metadata = {
                "export_version": "1.0",
                "world_id": "src_world",
                "user_id": "src_user",
                "image_count": len(images or {}),
                "subdirs": ["characters", "locations", "props", "scripts", "worlds"]
            }
            zipf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False))

        return zip_path

    def test_import_basic(self):
        """测试基本导入功能"""
        characters = [
            {"name": "导入角色A", "description": "测试角色"},
            {"name": "导入角色B", "description": "另一个角色"},
        ]
        zip_path = self._create_export_zip(characters=characters)

        result = self.fm.import_world(self.user_id, self.world_id, zip_path)

        self.assertEqual(result["characters"], 2)
        self.assertEqual(len(result["errors"]), 0)

        # 验证文件已写入
        base_path = self.fm._get_user_world_path(self.user_id, self.world_id)
        self.assertTrue((base_path / "characters" / "导入角色A.json").exists())
        self.assertTrue((base_path / "characters" / "导入角色B.json").exists())

        # 验证文件内容
        with open(base_path / "characters" / "导入角色A.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data["description"], "测试角色")

    def test_import_with_images(self):
        """测试导入包含图片"""
        images = {"test-img.png": b'\x89PNG\r\n\x1a\n' + b'\x00' * 50}
        characters = [
            {"name": "有图角色", "reference_image": "images/test-img.png"},
        ]
        zip_path = self._create_export_zip(characters=characters, images=images)

        result = self.fm.import_world(self.user_id, self.world_id, zip_path)

        self.assertEqual(result["images"], 1)
        self.assertEqual(result["characters"], 1)

        # 验证图片已复制到 upload 目录
        img_path = Path(self.tmp_dir) / "upload" / "character" / "pic" / "test-img.png"
        self.assertTrue(img_path.exists())

        # 验证角色 JSON 中的 URL 已还原
        base_path = self.fm._get_user_world_path(self.user_id, self.world_id)
        with open(base_path / "characters" / "有图角色.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data["reference_image"], "/upload/character/pic/test-img.png")

    def test_import_with_script_problem(self):
        """测试导入 script_problem.json"""
        script_problem = {"verdict": False, "problem": "导入的问题"}
        zip_path = self._create_export_zip(script_problem=script_problem)

        result = self.fm.import_world(self.user_id, self.world_id, zip_path)

        base_path = self.fm._get_user_world_path(self.user_id, self.world_id)
        problem_file = base_path / "script_problem.json"
        self.assertTrue(problem_file.exists())
        with open(problem_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data["problem"], "导入的问题")

    def test_import_multiple_subdirs(self):
        """测试导入多个子目录"""
        characters = [{"name": "角色1"}]
        locations = [{"name": "场景1"}]
        zip_path = self._create_export_zip(characters=characters, locations=locations)

        result = self.fm.import_world(self.user_id, self.world_id, zip_path)

        self.assertEqual(result["characters"], 1)
        self.assertEqual(result["locations"], 1)

    def test_import_image_already_exists(self):
        """测试图片已存在时不覆盖"""
        # 预先创建图片
        img_dir = Path(self.tmp_dir) / "upload" / "character" / "pic"
        img_dir.mkdir(parents=True, exist_ok=True)
        existing_img = img_dir / "existing.png"
        existing_img.write_bytes(b'ORIGINAL')

        images = {"existing.png": b'NEW_DATA'}
        zip_path = self._create_export_zip(images=images)

        result = self.fm.import_world(self.user_id, self.world_id, zip_path)

        # 图片不应被覆盖
        self.assertEqual(existing_img.read_bytes(), b'ORIGINAL')
        # 但计数仍为 1（因为 uploaded_images 会记录）
        self.assertEqual(result["images"], 0)  # 已存在，不写入


class TestExportImportRoundTrip(unittest.TestCase):
    """测试导出→导入的完整往返"""

    def setUp(self):
        self.export_dir = tempfile.mkdtemp(prefix="test_fm_export_rt_")
        self.import_dir = tempfile.mkdtemp(prefix="test_fm_import_rt_")
        self.fm_export = FileManager(base_dir=self.export_dir)
        self.fm_import = FileManager(base_dir=self.import_dir)
        self.user_id = "rt_user"
        self.world_id = "rt_world"

    def tearDown(self):
        shutil.rmtree(self.export_dir, ignore_errors=True)
        shutil.rmtree(self.import_dir, ignore_errors=True)

    def test_roundtrip_with_images(self):
        """测试导出再导入后数据一致"""
        # 准备导出数据
        base_path = self.fm_export._get_user_world_path(self.user_id, self.world_id)
        self.fm_export._ensure_directories(self.user_id, self.world_id)

        # 创建图片
        img_dir = Path(self.export_dir) / "upload" / "character" / "pic"
        img_dir.mkdir(parents=True, exist_ok=True)
        img_file = img_dir / "roundtrip-img.png"
        img_content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 200
        img_file.write_bytes(img_content)

        # 创建角色
        char_data = {
            "name": "往返角色",
            "description": "测试往返",
            "reference_image": "http://localhost:9003/upload/character/pic/roundtrip-img.png"
        }
        (base_path / "characters" / "往返角色.json").write_text(
            json.dumps(char_data, ensure_ascii=False), encoding='utf-8'
        )

        # 创建场景
        loc_data = {
            "name": "往返场景",
            "reference_images": [
                {"url": "http://localhost:9003/upload/character/pic/roundtrip-img.png", "angle": "front"}
            ]
        }
        (base_path / "locations" / "往返场景.json").write_text(
            json.dumps(loc_data, ensure_ascii=False), encoding='utf-8'
        )

        # 导出
        zip_path = self.fm_export.export_world(self.user_id, self.world_id)

        # 导入
        result = self.fm_import.import_world(self.user_id, self.world_id, zip_path)

        # 验证
        self.assertEqual(result["characters"], 1)
        self.assertEqual(result["locations"], 1)
        self.assertEqual(result["images"], 1)
        self.assertEqual(len(result["errors"]), 0)

        # 验证导入后的角色数据
        import_base = self.fm_import._get_user_world_path(self.user_id, self.world_id)
        with open(import_base / "characters" / "往返角色.json", 'r', encoding='utf-8') as f:
            imported_char = json.load(f)
            # URL 应该被还原为原始路径
            self.assertEqual(imported_char["reference_image"], "/upload/character/pic/roundtrip-img.png")
            self.assertEqual(imported_char["description"], "测试往返")

        # 验证图片已复制
        import_img = Path(self.import_dir) / "upload" / "character" / "pic" / "roundtrip-img.png"
        self.assertTrue(import_img.exists())
        self.assertEqual(import_img.read_bytes(), img_content)

        # 清理
        os.unlink(zip_path)


if __name__ == '__main__':
    unittest.main()
