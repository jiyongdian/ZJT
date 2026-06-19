"""
E2E 测试核心 fixtures。
提供浏览器、认证、API 客户端、测试数据工厂等 fixtures。
"""
import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import sync_playwright

# 将项目根目录加入 sys.path
AUTO_TEST_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = AUTO_TEST_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 将 helpers 目录加入 sys.path
HELPERS_DIR = Path(__file__).resolve().parent / "helpers"
sys.path.insert(0, str(HELPERS_DIR))

from helpers.page_objects import (
    AdminPage,
    IndexPage,
    MarketingAgentPage,
    ScriptWriterPage,
    WorkflowEditorPage,
    WorkflowListPage,
)


# ──────────────────────────── 辅助函数 ────────────────────────────


def extract_id(data: dict, id_type: str = None) -> str:
    """从响应数据中提取 ID，兼容多种字段名

    Args:
        data: 响应数据
        id_type: 指定 ID 类型 ("world", "character", "location", "workflow", "session")
    """
    # 如果指定了类型，优先返回对应的 ID
    type_field_map = {
        "world": "world_id",
        "character": "character_id",
        "location": "location_id",
        "workflow": "workflow_id",
        "session": "session_id",
    }

    if id_type and id_type in type_field_map:
        field = type_field_map[id_type]
        if field in data:
            return data[field]
        if "data" in data and isinstance(data["data"], dict) and field in data["data"]:
            return data["data"][field]

    # 通用提取
    return (
        data.get("id")
        or data.get("data", {}).get("id")
        or data.get("session_id")
        or data.get("world_id")
        or data.get("character_id")
        or data.get("location_id")
        or data.get("workflow_id")
        or data.get("data", {}).get("session_id")
        or ""
    )


def get_worlds_list(api_client) -> list:
    """获取世界列表"""
    resp = api_client.get("/api/worlds")
    if resp.status_code != 200:
        return []
    data = resp.json()
    # 响应格式: {"code": 0, "data": {"data": [...], "total": ...}}
    inner = data.get("data", data)
    if isinstance(inner, dict):
        return inner.get("data", [])
    return inner if isinstance(inner, list) else []


# ──────────────────────────── 配置 ────────────────────────────


@pytest.fixture(scope="session")
def e2e_config():
    """读取 test_config.json 配置文件"""
    config_path = AUTO_TEST_DIR / "test_config.json"
    if not config_path.exists():
        pytest.skip(f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def base_url(e2e_config):
    """服务器基础 URL"""
    return e2e_config["base_url"].rstrip("/")


# ──────────────────────────── 认证 ────────────────────────────


@pytest.fixture(scope="session")
def _login_data(e2e_config, base_url):
    """内部 fixture：一次登录获取 token 和 user_id。

    注意：登录接口会删除该用户所有旧 token 再创建新 token，
    因此必须只登录一次，避免多次登录导致 token 失效。
    """
    creds = e2e_config["credentials"]["primary"]
    try:
        resp = httpx.post(
            f"{base_url}/api/auth/login",
            json={"phone": creds["phone"], "password": creds["password"]},
            timeout=10,
        )
    except (httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout) as e:
        pytest.skip(f"服务器不可用，跳过测试: {e}")
    if resp.status_code != 200:
        pytest.skip(f"登录失败，状态码: {resp.status_code}, 响应: {resp.text}")
    data = resp.json()
    inner = data.get("data", data)
    token = inner.get("token") or data.get("token") or data.get("access_token")
    uid = inner.get("user_id") or data.get("user_id")
    if not token:
        pytest.skip(f"登录响应中未找到 token: {data}")
    if not uid:
        pytest.skip(f"登录响应中未找到 user_id: {data}")
    return {"token": token, "user_id": str(uid)}


@pytest.fixture(scope="session")
def auth_token(_login_data):
    """通过 API 登录获取 token（session scope，只登录一次）"""
    return _login_data["token"]


@pytest.fixture(scope="session")
def user_id(_login_data):
    """通过 API 登录获取 user_id"""
    return _login_data["user_id"]


@pytest.fixture(scope="session")
def auth_headers(auth_token, user_id):
    """构造认证 headers"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-User-Id": str(user_id),
    }


def refresh_login(e2e_config, base_url):
    """重新登录获取新 token（当 token 失效时使用）"""
    creds = e2e_config["credentials"]["primary"]
    resp = httpx.post(
        f"{base_url}/api/auth/login",
        json={"phone": creds["phone"], "password": creds["password"]},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    inner = data.get("data", data)
    token = inner.get("token") or data.get("token") or data.get("access_token")
    uid = inner.get("user_id") or data.get("user_id")
    if token and uid:
        return {"token": token, "user_id": str(uid)}
    return None


@pytest.fixture
def api_client_with_refresh(base_url, auth_headers, e2e_config):
    """httpx API 客户端，支持 token 失效时自动刷新"""
    import time

    client = httpx.Client(
        base_url=base_url,
        headers=auth_headers,
        timeout=httpx.Timeout(10.0),
    )
    yield client
    client.close()


# ──────────────────────────── 浏览器 ────────────────────────────


@pytest.fixture(scope="session")
def browser():
    """Playwright chromium 浏览器实例（session scope）"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        yield browser
        browser.close()


@pytest.fixture
def browser_context(browser, auth_token, user_id, base_url):
    """浏览器上下文，注入 localStorage 认证信息"""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
    )
    # 注入 localStorage 认证信息，跳过 UI 登录
    context.add_init_script(f"""
        localStorage.setItem('auth_token', '{auth_token}');
        localStorage.setItem('user_id', '{user_id}');
    """)
    yield context
    context.close()


@pytest.fixture
def page(browser_context):
    """每个测试独立的页面实例"""
    p = browser_context.new_page()
    yield p
    p.close()


@pytest.fixture
def editor_page(browser, auth_token, user_id, base_url):
    """工作流编辑器专用页面，已注入认证信息。

    复用 session-scoped browser 实例，避免创建多个 sync_playwright 上下文导致 asyncio 冲突。
    通过 add_init_script 在页面脚本运行前注入 localStorage。
    """
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
    )
    # 在页面脚本运行前注入认证信息
    context.add_init_script(f"""
        localStorage.setItem('auth_token', '{auth_token}');
        localStorage.setItem('user_id', '{user_id}');
    """)
    page = context.new_page()

    yield page
    page.close()
    context.close()


# ──────────────────────────── API 客户端 ────────────────────────────


@pytest.fixture
def api_client(base_url, auth_headers):
    """httpx 异步 API 客户端（非阻塞）"""
    client = httpx.Client(
        base_url=base_url,
        headers=auth_headers,
        timeout=httpx.Timeout(10.0),
    )
    yield client
    client.close()


# ──────────────────────────── Page Objects ────────────────────────────


@pytest.fixture
def index_page(page, base_url):
    return IndexPage(page, base_url)


@pytest.fixture
def script_writer_page(page, base_url):
    return ScriptWriterPage(page, base_url)


@pytest.fixture
def sw_page(browser, auth_token, user_id, base_url, api_client):
    """剧本编辑器专用页面，URL 带 user_id 和 world_id。

    复用 session-scoped browser，注入认证信息，
    并自动获取 world_id 传入 URL 参数。
    """
    # 获取 world_id
    worlds_resp = api_client.get("/api/worlds")
    worlds_data = worlds_resp.json()
    inner = worlds_data.get("data", worlds_data)
    worlds = inner.get("data", []) if isinstance(inner, dict) else inner
    world_id = str(worlds[0]["id"]) if worlds else "1"

    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
    )
    context.add_init_script(f"""
        localStorage.setItem('auth_token', '{auth_token}');
        localStorage.setItem('user_id', '{user_id}');
    """)
    p = context.new_page()
    # 拦截算力 API 防止重定向到登录页
    import json as _json
    def _power_handler(route):
        route.fulfill(
            status=200, content_type="application/json",
            body=_json.dumps({"success": True, "data": {"computing_power": 9999}}),
        )
    p.route("**/api/user/computing_power", _power_handler)
    page_obj = ScriptWriterPage(p, base_url)
    # 将 world_id 附加到 page_obj 供测试使用
    page_obj.world_id = world_id
    page_obj.user_id = str(user_id)
    page_obj.auth_token = auth_token
    yield page_obj
    p.close()
    context.close()


@pytest.fixture
def workflow_list_page(page, base_url):
    return WorkflowListPage(page, base_url)


@pytest.fixture
def workflow_editor_page(page, base_url):
    return WorkflowEditorPage(page, base_url)


@pytest.fixture
def marketing_agent_page(page, base_url):
    return MarketingAgentPage(page, base_url)


@pytest.fixture
def admin_page(page, base_url):
    return AdminPage(page, base_url)


@pytest.fixture
def admin_browser_page(browser, auth_token, user_id, base_url):
    """管理后台专用页面，注入认证信息并 mock 所有 admin API。

    admin.js 使用 axios + Bearer token 认证，但 pytest 环境下
    add_init_script 的 token 在页面 API 调用时可能尚未就绪，
    导致 401 重定向。通过 page.route() mock 所有 admin API 绕过此问题。
    """
    import json as _json

    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
    )
    context.add_init_script(f"""
        localStorage.setItem('auth_token', '{auth_token}');
        localStorage.setItem('user_id', '{user_id}');
        localStorage.setItem('phone', '15088613226');
    """)
    p = context.new_page()

    # Mock 所有 admin API 端点
    def _mock_admin_api(route):
        url = route.request.url
        path = url.split(base_url)[-1].split("?")[0] if base_url in url else url

        mock_responses = {
            "/api/admin/dashboard": {
                "code": 0,
                "data": {
                    "total_users": 100,
                    "active_workflows_3d": 5,
                    "is_community_edition": False,
                },
            },
            "/api/admin/dashboard/monthly-active-users": {
                "code": 0,
                "data": {"monthly_active_users": 50},
            },
            "/api/admin/dashboard/model-analysis": {
                "code": 0,
                "data": {
                    "models": [
                        {"model_name": "gpt-4", "total": 100, "success": 95},
                        {"model_name": "claude-3", "total": 80, "success": 78},
                    ]
                },
            },
            "/api/admin/users": {
                "code": 0,
                "data": {
                    "data": [
                        {
                            "user_id": "1",
                            "phone": "15088613226",
                            "nickname": "测试用户",
                            "role": "admin",
                            "status": 1,
                            "computing_power": 9999,
                            "create_at": "2025-01-01",
                        },
                        {
                            "user_id": "2",
                            "phone": "13800138000",
                            "nickname": "普通用户",
                            "role": "user",
                            "status": 1,
                            "computing_power": 100,
                            "create_at": "2025-01-02",
                        },
                    ],
                    "total": 2,
                },
            },
            "/api/admin/config": {
                "code": 0,
                "data": {
                    "data": [
                        {
                            "config_key": "llm_model",
                            "config_value": "gpt-4",
                            "description": "LLM模型",
                            "is_public": True,
                            "editable": True,
                            "value_type": "str",
                        },
                        {
                            "config_key": "max_tokens",
                            "config_value": "4096",
                            "description": "最大token数",
                            "is_public": True,
                            "editable": True,
                            "value_type": "int",
                        },
                    ],
                    "total": 2,
                },
            },
            "/api/admin/config/quick-configs": {
                "code": 0,
                "data": {},
            },
            "/api/admin/config/raw": {
                "code": 0,
                "data": {},
            },
            "/api/admin/implementation-configs": {
                "code": 0,
                "data": [
                    {
                        "group_name": "text_to_image",
                        "implementations": [
                            {
                                "id": 1,
                                "name": "sd-webui",
                                "sort_order": 1,
                                "power_cost": 10,
                            }
                        ],
                    }
                ],
            },
            "/api/admin/implementation-powers": {
                "code": 0,
                "data": {"powers": []},
            },
            "/api/notifications/poll": {"code": 0, "data": {"notifications": [], "unread_count": 0, "version_update": None, "missing_binaries": []}},
            "/api/notifications/admin/list": {
                "code": 0,
                "data": {"notifications": [], "total": 0},
            },
            "/api/system/server-config": {"code": 0, "data": {}},
        }

        # 匹配路径
        for api_path, resp_data in mock_responses.items():
            if path == api_path or path.startswith(api_path + "/"):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=_json.dumps(resp_data),
                )
                return

        # 用户详情等动态路径
        if path.startswith("/api/admin/users/") and "/power" in path:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps({"code": 0, "data": {}}),
            )
            return
        if path.startswith("/api/admin/users/") and "/role" in path:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps({"code": 0, "data": {}}),
            )
            return
        if path.startswith("/api/admin/users/") and "/status" in path:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps({"code": 0, "data": {}}),
            )
            return
        if path.startswith("/api/admin/users/"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "user_id": "1",
                            "phone": "15088613226",
                            "nickname": "测试用户",
                            "role": "admin",
                            "status": 1,
                            "computing_power": 9999,
                        },
                    }
                ),
            )
            return

        # 配置详情
        if path.startswith("/api/admin/config/") and path != "/api/admin/config":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "config_key": "test_key",
                            "config_value": "test_value",
                        },
                    }
                ),
            )
            return

        # 其他 admin API 默认返回成功
        if "/api/admin/" in path or "/api/notifications/" in path:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps({"code": 0, "data": {}}),
            )
            return

        # 非 admin API 放行
        route.continue_()

    p.route("**/api/**", _mock_admin_api)

    page_obj = AdminPage(p, base_url)
    page_obj.user_id = str(user_id)
    page_obj.auth_token = auth_token
    yield page_obj
    p.close()
    context.close()


# ──────────────────────────── 测试数据工厂 ────────────────────────────


@pytest.fixture
def test_world(api_client):
    """创建测试世界，测试后清理"""
    resp = api_client.post(
        "/api/worlds",
        json={"name": "E2E测试世界", "description": "自动化测试创建的世界"},
    )
    if resp.status_code not in (200, 201):
        pytest.fail(f"创建测试世界失败: {resp.status_code} {resp.text}")
    data = resp.json()
    world_id = extract_id(data, "world")
    yield {"id": world_id, "data": data}
    # 清理
    try:
        api_client.delete(f"/api/worlds/{world_id}")
    except Exception:
        pass


@pytest.fixture
def test_character(api_client, test_world):
    """创建测试角色，测试后清理"""
    resp = api_client.post(
        "/api/characters",
        data={
            "world_id": test_world["id"],
            "name": "E2E测试角色",
        },
    )
    if resp.status_code not in (200, 201):
        pytest.fail(f"创建测试角色失败: {resp.status_code} {resp.text}")
    data = resp.json()
    char_id = extract_id(data, "character")
    yield {"id": char_id, "data": data}
    try:
        api_client.delete(f"/api/characters/{char_id}")
    except Exception:
        pass


@pytest.fixture
def test_location(api_client, test_world):
    """创建测试场景，测试后清理"""
    resp = api_client.post(
        "/api/locations",
        data={
            "world_id": test_world["id"],
            "name": "E2E测试场景",
        },
    )
    if resp.status_code not in (200, 201):
        pytest.fail(f"创建测试场景失败: {resp.status_code} {resp.text}")
    data = resp.json()
    loc_id = extract_id(data, "location")
    yield {"id": loc_id, "data": data}
    try:
        api_client.delete(f"/api/locations/{loc_id}")
    except Exception:
        pass


@pytest.fixture
def test_workflow(api_client):
    """创建测试工作流，测试后清理"""
    resp = api_client.post(
        "/api/video-workflow/create",
        json={"name": "E2E测试工作流", "description": "自动化测试创建的工作流"},
    )
    if resp.status_code not in (200, 201):
        pytest.fail(f"创建测试工作流失败: {resp.status_code} {resp.text}")
    data = resp.json()
    wf_id = extract_id(data, "workflow")
    yield {"id": wf_id, "data": data}
    try:
        api_client.delete(f"/api/video-workflow/{wf_id}")
    except Exception:
        pass


@pytest.fixture
def test_session_id(api_client, auth_token, user_id):
    """创建测试会话，测试后清理"""
    # 先获取一个世界 ID
    worlds = get_worlds_list(api_client)
    world_id = worlds[0]["id"] if worlds else "1"

    resp = api_client.post(
        "/api/session/create",
        json={
            "user_id": str(user_id),
            "world_id": str(world_id),
            "auth_token": auth_token,
            "session_type": 1,
        },
    )
    if resp.status_code not in (200, 201):
        pytest.fail(f"创建测试会话失败: {resp.status_code} {resp.text}")
    data = resp.json()
    sid = extract_id(data, "session")
    yield sid
    try:
        api_client.delete(f"/api/session/{sid}")
    except Exception:
        pass


@pytest.fixture
def marketing_session(api_client, auth_token, user_id):
    """创建营销会话（session_type=2），测试后清理"""
    worlds = get_worlds_list(api_client)
    world_id = worlds[0]["id"] if worlds else "1"

    resp = api_client.post(
        "/api/session/create",
        json={
            "user_id": str(user_id),
            "world_id": str(world_id),
            "auth_token": auth_token,
            "session_type": 2,
        },
    )
    if resp.status_code not in (200, 201):
        pytest.fail(f"创建营销会话失败: {resp.status_code} {resp.text}")
    data = resp.json()
    sid = extract_id(data, "session")
    yield {"id": sid, "data": data}
    try:
        api_client.delete(f"/api/session/{sid}")
    except Exception:
        pass
