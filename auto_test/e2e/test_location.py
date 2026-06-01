"""
场景管理 CRUD E2E 测试（P0）。

覆盖端点：
- POST   /api/locations          创建场景（Form data）
- GET    /api/locations           场景列表（需 world_id 参数）
- PUT    /api/locations/{id}      更新场景
- DELETE /api/locations/{id}      删除场景
"""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.location]


@pytest.mark.p0
class TestLocationCreate:
    """POST /api/locations"""

    def test_create_location(self, api_client, test_world):
        """P0: 创建场景，返回 200/201 且包含 id"""
        resp = api_client.post(
            "/api/locations",
            data={
                "world_id": test_world["id"],
                "name": "新建场景",
            },
        )
        assert resp.status_code in (200, 201), f"创建场景失败: {resp.status_code} {resp.text}"
        data = resp.json()
        loc_id = data.get("id") or data.get("location_id") or data.get("data", {}).get("id")
        assert loc_id, f"响应中未找到场景 id: {data}"
        # 清理
        api_client.delete(f"/api/locations/{loc_id}")


@pytest.mark.p0
class TestLocationList:
    """GET /api/locations"""

    def test_list_locations(self, api_client, test_location, test_world):
        """P0: 获取场景列表，返回 200 且为列表"""
        resp = api_client.get("/api/locations", params={"world_id": test_world["id"]})
        assert resp.status_code == 200, f"获取场景列表失败: {resp.status_code} {resp.text}"
        body = resp.json()
        inner = body.get("data", body)
        locations = inner.get("data", []) if isinstance(inner, dict) else inner
        assert isinstance(locations, list), f"场景列表应为 list，实际: {type(locations)}"


@pytest.mark.p0
class TestLocationDetail:
    """GET /api/locations（从列表中定位目标场景）"""

    def test_get_location_detail(self, api_client, test_location, test_world):
        """P0: 从列表中查找刚创建的场景，验证 name 字段"""
        resp = api_client.get("/api/locations", params={"world_id": test_world["id"]})
        assert resp.status_code == 200
        body = resp.json()
        inner = body.get("data", body)
        locations = inner.get("data", []) if isinstance(inner, dict) else inner

        target_id = test_location["id"]
        found = [loc for loc in locations if str(loc.get("id", "")) == str(target_id)]
        assert found, f"场景列表中未找到 id={target_id} 的场景"
        assert found[0].get("name") == "E2E测试场景"


@pytest.mark.p0
class TestLocationUpdate:
    """PUT /api/locations/{id}"""

    def test_update_location(self, api_client, test_location):
        """P0: 更新场景名称，返回 200"""
        loc_id = test_location["id"]
        payload = {"name": "已更新场景", "description": "更新后的描述"}
        resp = api_client.put(f"/api/locations/{loc_id}", json=payload)
        assert resp.status_code == 200, f"更新场景失败: {resp.status_code} {resp.text}"


@pytest.mark.p0
class TestLocationDelete:
    """DELETE /api/locations/{id}"""

    def test_delete_location(self, api_client, test_world):
        """P0: 删除场景，返回 200"""
        # 先创建一个专门用于删除测试的场景
        create_resp = api_client.post(
            "/api/locations",
            data={
                "world_id": test_world["id"],
                "name": "待删除场景",
            },
        )
        assert create_resp.status_code in (200, 201)
        data = create_resp.json()
        loc_id = data.get("id") or data.get("location_id") or data.get("data", {}).get("id")
        assert loc_id

        del_resp = api_client.delete(f"/api/locations/{loc_id}")
        assert del_resp.status_code in (200, 204), f"删除场景失败: {del_resp.status_code} {del_resp.text}"


# ────────────────── P1 测试 ──────────────────


class TestLocationListByWorld:
    """GET /api/locations?world_id=xxx"""

    @pytest.mark.p1
    def test_location_list_by_world(self, api_client, test_location, test_world):
        """P1: 按 world_id 筛选场景列表"""
        resp = api_client.get("/api/locations", params={"world_id": test_world["id"]})
        assert resp.status_code == 200, f"按世界筛选场景失败: {resp.status_code} {resp.text}"
        body = resp.json()
        inner = body.get("data", body)
        locations = inner.get("data", []) if isinstance(inner, dict) else inner
        assert isinstance(locations, list), f"场景列表应为 list，实际: {type(locations)}"


class TestLocationNameEmpty:
    """POST /api/locations - 空名称校验"""

    @pytest.mark.p1
    def test_location_name_empty(self, api_client, test_world):
        """P1: 空名称创建场景应返回非200"""
        resp = api_client.post(
            "/api/locations",
            data={"world_id": test_world["id"], "name": ""},
        )
        assert resp.status_code != 200, "空名称创建场景应返回非200状态码"
