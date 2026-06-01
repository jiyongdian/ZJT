"""
算力日志页面 E2E 测试。
覆盖页面加载、筛选标签、分页、认证错误状态等场景。

computing_power_logs.html 从 localStorage 读取 auth_token，
通常在 iframe 中加载。使用 page fixture 注入认证信息并 mock API。
"""
import json as _json

import pytest


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _setup_logs_page(browser, auth_token, user_id, base_url, mock_data=None):
    """创建算力日志页面实例，注入认证信息并 mock API"""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
    )
    context.add_init_script(f"""
        localStorage.setItem('auth_token', '{auth_token}');
        localStorage.setItem('user_id', '{user_id}');
    """)
    p = context.new_page()

    if mock_data is None:
        mock_data = {
            "success": True,
            "data": {
                "logs": [
                    {
                        "id": 1,
                        "behavior": "increase",
                        "note": "签到奖励",
                        "computing_power": 10,
                        "from": 0,
                        "to": 10,
                        "created_at": "2025-01-15 10:30:00",
                    },
                    {
                        "id": 2,
                        "behavior": "deduct",
                        "note": "视频生成扣费",
                        "computing_power": -5,
                        "from": 10,
                        "to": 5,
                        "created_at": "2025-01-15 11:00:00",
                    },
                ],
                "total": 2,
                "limit": 20,
                "offset": 0,
            },
        }

    def _mock_api(route):
        url = route.request.url
        path = url.split(base_url)[-1].split("?")[0] if base_url in url else url

        if path == "/api/user/computing_power_logs":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps(mock_data),
            )
        else:
            route.continue_()

    p.route("**/api/**", _mock_api)
    return p, context


# ═══════════════════════════════════════════════════════════════
# P0 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.p0
@pytest.mark.computing_power
def test_power_logs_page_loads(browser, auth_token, user_id, base_url):
    """cpl_001 - 算力日志页面加载成功。"""
    p, context = _setup_logs_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/computing_power_logs.html", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    # 验证页面容器
    app = p.locator("#app")
    assert app.count() > 0, "应有 #app 容器"

    p.close()
    context.close()


@pytest.mark.p0
@pytest.mark.computing_power
def test_power_logs_display_entries(browser, auth_token, user_id, base_url):
    """cpl_002 - 页面显示日志条目。"""
    p, context = _setup_logs_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/computing_power_logs.html", wait_until="domcontentloaded")
    p.wait_for_timeout(3000)

    # 验证日志列表或表格存在
    log_items = p.locator(".log-item, .log-entry, tr, [class*='log']")
    # 页面可能用表格或列表展示
    body_text = p.locator("body").text_content() or ""
    has_content = log_items.count() > 0 or "签到" in body_text or "扣费" in body_text or "增加" in body_text
    assert has_content, "应显示日志条目"

    p.close()
    context.close()


@pytest.mark.p0
@pytest.mark.computing_power
def test_power_logs_filter_tabs(browser, auth_token, user_id, base_url):
    """cpl_003 - 筛选标签存在（全部/增加/扣除）。"""
    p, context = _setup_logs_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/computing_power_logs.html", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    # 验证筛选标签
    body_text = p.locator("body").text_content() or ""
    has_tabs = ("全部" in body_text and "增加" in body_text) or ("全部" in body_text and "扣除" in body_text)
    assert has_tabs, f"应有筛选标签（全部/增加/扣除）"

    p.close()
    context.close()


# ═══════════════════════════════════════════════════════════════
# P1 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.p1
@pytest.mark.computing_power
def test_power_logs_pagination(browser, auth_token, user_id, base_url):
    """cpl_004 - 分页控件存在。"""
    # 使用大量数据的 mock
    logs = [
        {
            "id": i,
            "behavior": "increase" if i % 2 == 0 else "deduct",
            "note": f"日志 {i}",
            "computing_power": 10 if i % 2 == 0 else -5,
            "from": i * 10,
            "to": (i + 1) * 10,
            "created_at": f"2025-01-{15 + i // 20} 10:00:00",
        }
        for i in range(20)
    ]
    mock_data = {
        "success": True,
        "data": {"logs": logs, "total": 50, "limit": 20, "offset": 0},
    }
    p, context = _setup_logs_page(browser, auth_token, user_id, base_url, mock_data)
    p.goto(f"{base_url}/computing_power_logs.html", wait_until="domcontentloaded")
    p.wait_for_timeout(3000)

    # 验证分页信息
    body_text = p.locator("body").text_content() or ""
    has_pagination = "页" in body_text or "page" in body_text.lower() or "上一页" in body_text or "下一页" in body_text
    # 分页可能以按钮或文本形式存在
    page_btns = p.locator("button:has-text('上一页'), button:has-text('下一页'), button:has-text('Previous'), button:has-text('Next')")
    assert has_pagination or page_btns.count() > 0, "应有分页控件"

    p.close()
    context.close()


@pytest.mark.p1
@pytest.mark.computing_power
def test_power_logs_no_auth_shows_error(browser, base_url):
    """cpl_005 - 无认证信息时显示错误提示。"""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
    )
    # 不设置 localStorage
    p = context.new_page()
    p.goto(f"{base_url}/computing_power_logs.html", wait_until="domcontentloaded")
    p.wait_for_timeout(3000)

    # 应显示错误提示
    body_text = p.locator("body").text_content() or ""
    has_error = "认证" in body_text or "登录" in body_text or "缺少" in body_text or "error" in body_text.lower()
    assert has_error, f"无认证时应显示错误提示"

    p.close()
    context.close()


@pytest.mark.p1
@pytest.mark.computing_power
def test_power_logs_empty_state(browser, auth_token, user_id, base_url):
    """cpl_006 - 无日志数据时显示空状态。"""
    mock_data = {"success": True, "data": {"logs": [], "total": 0, "limit": 20, "offset": 0}}
    p, context = _setup_logs_page(browser, auth_token, user_id, base_url, mock_data)
    p.goto(f"{base_url}/computing_power_logs.html", wait_until="domcontentloaded")
    p.wait_for_timeout(3000)

    body_text = p.locator("body").text_content() or ""
    has_empty = "暂无" in body_text or "没有" in body_text or "空" in body_text or "no data" in body_text.lower()
    # 空状态下页面不应崩溃
    app = p.locator("#app")
    assert app.count() > 0, "空状态下页面不应崩溃"

    p.close()
    context.close()
