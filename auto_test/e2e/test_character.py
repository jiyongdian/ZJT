"""
角色管理 CRUD E2E 测试（P0）。

覆盖端点：
- POST   /api/characters            创建角色（Form data）
- GET    /api/characters            角色列表（需 world_id 参数）
- POST   /api/characters/update     更新角色（Form data）
- DELETE /api/characters/{id}       删除角色
"""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.character]


@pytest.mark.p0
class TestCharacterCreate:
    """POST /api/characters"""

    def test_create_character(self, api_client, test_world):
        """P0: 创建角色，返回 200/201 且包含 id"""
        resp = api_client.post(
            "/api/characters",
            data={
                "world_id": test_world["id"],
                "name": "新建角色",
            },
        )
        assert resp.status_code in (200, 201), f"创建角色失败: {resp.status_code} {resp.text}"
        data = resp.json()
        char_id = data.get("id") or data.get("character_id") or data.get("data", {}).get("id")
        assert char_id, f"响应中未找到角色 id: {data}"
        # 清理
        api_client.delete(f"/api/characters/{char_id}")


@pytest.mark.p0
class TestCharacterList:
    """GET /api/characters"""

    def test_list_characters(self, api_client, test_character, test_world):
        """P0: 获取角色列表，返回 200 且为列表"""
        resp = api_client.get("/api/characters", params={"world_id": test_world["id"]})
        assert resp.status_code == 200, f"获取角色列表失败: {resp.status_code} {resp.text}"
        body = resp.json()
        # 响应格式: {"code": 0, "data": {"data": [...], "total": ...}}
        inner = body.get("data", body)
        characters = inner.get("data", []) if isinstance(inner, dict) else inner
        assert isinstance(characters, list), f"角色列表应为 list，实际: {type(characters)}"


@pytest.mark.p0
class TestCharacterUpdate:
    """POST /api/characters/update"""

    def test_update_character(self, api_client, test_character):
        """P0: 更新角色信息，返回 200"""
        char_id = test_character["id"]
        resp = api_client.post(
            "/api/characters/update",
            data={
                "character_id": char_id,
                "name": "已更新角色",
            },
        )
        assert resp.status_code == 200, f"更新角色失败: {resp.status_code} {resp.text}"


@pytest.mark.p0
class TestCharacterDelete:
    """DELETE /api/characters/{id}"""

    def test_delete_character(self, api_client, test_world):
        """P0: 删除角色，返回 200"""
        # 先创建一个专门用于删除测试的角色
        create_resp = api_client.post(
            "/api/characters",
            data={
                "world_id": test_world["id"],
                "name": "待删除角色",
            },
        )
        assert create_resp.status_code in (200, 201)
        data = create_resp.json()
        char_id = data.get("id") or data.get("character_id") or data.get("data", {}).get("id")
        assert char_id

        del_resp = api_client.delete(f"/api/characters/{char_id}")
        assert del_resp.status_code in (200, 204), f"删除角色失败: {del_resp.status_code} {del_resp.text}"


# ────────────────── P1 测试 ──────────────────


class TestCharacterGetById:
    """GET /api/characters/{id}"""

    @pytest.mark.p1
    def test_get_character_by_id(self, api_client, test_character, test_world):
        """P1: 通过 ID 获取角色详情"""
        char_id = test_character["id"]
        # 先从列表中查找该角色（角色可能没有独立的 GET 端点）
        resp = api_client.get("/api/characters", params={"world_id": test_world["id"]})
        assert resp.status_code == 200, f"获取角色列表失败: {resp.status_code} {resp.text}"
        body = resp.json()
        inner = body.get("data", body)
        characters = inner.get("data", []) if isinstance(inner, dict) else inner
        found = [c for c in characters if str(c.get("id", "")) == str(char_id)]
        assert found, f"角色列表中未找到 id={char_id} 的角色"
        assert found[0].get("name") == "E2E测试角色"


class TestCharacterListByWorld:
    """GET /api/characters?world_id=xxx"""

    @pytest.mark.p1
    def test_character_list_by_world(self, api_client, test_character, test_world):
        """P1: 按 world_id 筛选角色列表"""
        resp = api_client.get("/api/characters", params={"world_id": test_world["id"]})
        assert resp.status_code == 200, f"按世界筛选角色失败: {resp.status_code} {resp.text}"
        body = resp.json()
        inner = body.get("data", body)
        characters = inner.get("data", []) if isinstance(inner, dict) else inner
        assert isinstance(characters, list), f"角色列表应为 list，实际: {type(characters)}"
        # 验证列表中的角色属于该世界
        for c in characters:
            c_world_id = c.get("world_id") or c.get("world", {}).get("id")
            if c_world_id is not None:
                assert str(c_world_id) == str(test_world["id"]), f"角色 world_id 不匹配: {c}"
