"""
世界管理 CRUD E2E 测试（P0）。

覆盖端点：
- POST   /api/worlds          创建世界
- GET    /api/worlds           世界列表
- PUT    /api/worlds/{id}      更新世界
- DELETE /api/worlds/{id}      删除世界
"""
import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.world]


# ────────────────── 创建 ──────────────────


@pytest.mark.p0
class TestWorldCreate:
    """POST /api/worlds"""

    def test_create_world(self, api_client):
        """P0: 创建世界，返回 200/201 且包含 id"""
        payload = {"name": "新建世界", "description": "用于创建测试"}
        resp = api_client.post("/api/worlds", json=payload)
        assert resp.status_code in (200, 201), f"创建世界失败: {resp.status_code} {resp.text}"

        data = resp.json()
        world_id = data.get("id") or data.get("world_id") or data.get("data", {}).get("id")
        assert world_id, f"响应中未找到世界 id: {data}"

        # 清理
        api_client.delete(f"/api/worlds/{world_id}")


# ────────────────── 列表 ──────────────────


@pytest.mark.p0
class TestWorldList:
    """GET /api/worlds"""

    def test_list_worlds(self, api_client, test_world):
        """P0: 获取世界列表，返回 200 且包含数据"""
        resp = api_client.get("/api/worlds")
        assert resp.status_code == 200, f"获取世界列表失败: {resp.status_code} {resp.text}"

        body = resp.json()
        # 响应格式: {"code": 0, "data": {"data": [...], "total": ...}}
        inner = body.get("data", body)
        worlds = inner.get("data", []) if isinstance(inner, dict) else inner
        assert isinstance(worlds, list), f"世界列表应为 list，实际: {type(worlds)}"


# ────────────────── 获取详情（从列表中查找） ──────────────────


@pytest.mark.p0
class TestWorldDetail:
    """GET /api/worlds（从列表中定位目标世界）"""

    def test_get_world_detail(self, api_client, test_world):
        """P0: 从列表中查找刚创建的世界，验证 name 字段"""
        resp = api_client.get("/api/worlds")
        assert resp.status_code == 200

        body = resp.json()
        inner = body.get("data", body)
        worlds = inner.get("data", []) if isinstance(inner, dict) else inner

        target_id = test_world["id"]
        found = [w for w in worlds if str(w.get("id", "")) == str(target_id)]
        assert found, f"世界列表中未找到 id={target_id} 的世界"
        assert found[0].get("name") == "E2E测试世界"


# ────────────────── 更新 ──────────────────


@pytest.mark.p0
class TestWorldUpdate:
    """PUT /api/worlds/{id}"""

    def test_update_world(self, api_client, test_world):
        """P0: 更新世界名称，返回 200"""
        world_id = test_world["id"]
        payload = {"name": "已更新世界", "description": "更新后的描述"}
        resp = api_client.put(f"/api/worlds/{world_id}", json=payload)
        assert resp.status_code == 200, f"更新世界失败: {resp.status_code} {resp.text}"


# ────────────────── 删除 ──────────────────


@pytest.mark.p0
class TestWorldDelete:
    """DELETE /api/worlds/{id}"""

    def test_delete_world(self, api_client):
        """P0: 删除世界，返回 200"""
        # 先创建一个专门用于删除测试的世界
        create_resp = api_client.post(
            "/api/worlds",
            json={"name": "待删除世界", "description": "删除测试用"},
        )
        assert create_resp.status_code in (200, 201)
        data = create_resp.json()
        world_id = data.get("id") or data.get("world_id") or data.get("data", {}).get("id")
        assert world_id

        del_resp = api_client.delete(f"/api/worlds/{world_id}")
        assert del_resp.status_code in (200, 204), f"删除世界失败: {del_resp.status_code} {del_resp.text}"


# ────────────────── P1 测试 ──────────────────


class TestWorldGetById:
    """通过列表接口验证世界详情"""

    @pytest.mark.p1
    def test_get_world_by_id(self, api_client, test_world):
        """P1: 从列表中通过 ID 查找世界，验证 name 匹配"""
        world_id = test_world["id"]
        # 该 API 无 GET /api/worlds/{id} 端点，通过列表查找
        resp = api_client.get("/api/worlds?page=1&page_size=100")
        assert resp.status_code == 200, f"获取世界列表失败: {resp.status_code} {resp.text}"
        body = resp.json()
        inner = body.get("data", body)
        worlds = inner.get("data", []) if isinstance(inner, dict) else inner
        found = [w for w in worlds if str(w.get("id")) == str(world_id)]
        assert found, f"列表中未找到世界 id={world_id}"
        assert found[0].get("name") == "E2E测试世界", f"世界名称不匹配: {found[0]}"


class TestWorldNameEmpty:
    """POST /api/worlds - 空名称校验"""

    @pytest.mark.p1
    def test_world_name_empty(self, api_client):
        """P1: 空名称创建世界应返回非200"""
        resp = api_client.post("/api/worlds", json={"name": "", "description": "空名称测试"})
        assert resp.status_code != 200, "空名称创建世界应返回非200状态码"
