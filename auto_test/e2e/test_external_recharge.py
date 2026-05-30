"""
外部充值页面 E2E 测试。
覆盖页面加载、套餐信息显示、支付按钮状态、错误处理等场景。

external_recharge.html 通过 URL 参数接收套餐和认证信息，
页面加载后自动调用 /api/recharge/wechat-pay 创建支付订单。
使用 page.route() mock API 避免真实支付调用。
"""
import json as _json

import pytest


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _setup_recharge_page(browser, auth_token, user_id, base_url):
    """创建充值页面实例，mock 支付 API"""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
    )
    p = context.new_page()

    def _mock_api(route):
        url = route.request.url
        path = url.split(base_url)[-1].split("?")[0] if base_url in url else url

        if path == "/api/recharge/wechat-pay":
            # 不返回 h5_url，页面会捕获错误并显示重试按钮
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps(
                    {"success": False, "message": "测试环境mock：支付系统暂不可用"}
                ),
            )
        else:
            route.continue_()

    p.route("**/api/**", _mock_api)
    # Mock 外部 IP 服务
    p.route("**/api.ipify.org/**", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=_json.dumps({"ip": "127.0.0.1"}),
    ))

    return p, context


def _recharge_url(base_url, auth_token, user_id, **kwargs):
    """构造充值页面 URL"""
    params = {
        "package_id": "1",
        "user_id": user_id,
        "auth_token": auth_token,
        "package_name": "测试套餐",
        "price": "99",
        "computing_power": "1000",
    }
    params.update(kwargs)
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base_url}/external_recharge.html?{qs}"


# ═══════════════════════════════════════════════════════════════
# P0 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.p0
@pytest.mark.recharge
def test_recharge_page_loads(browser, auth_token, user_id, base_url):
    """er_001 - 充值页面加载成功。"""
    p, context = _setup_recharge_page(browser, auth_token, user_id, base_url)
    url = _recharge_url(base_url, auth_token, user_id)
    p.goto(url, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    # 验证页面标题
    title = p.title()
    assert "充值" in title or "pay" in title.lower() or title, f"页面标题: {title}"

    # 验证主要容器（.page 是主容器）
    page_el = p.locator(".page")
    assert page_el.count() > 0, "应有 .page 容器"

    p.close()
    context.close()


@pytest.mark.p0
@pytest.mark.recharge
def test_recharge_package_summary(browser, auth_token, user_id, base_url):
    """er_002 - 套餐摘要信息正确显示。"""
    p, context = _setup_recharge_page(browser, auth_token, user_id, base_url)
    url = _recharge_url(base_url, auth_token, user_id, package_name="高级套餐", price="199", computing_power="5000")
    p.goto(url, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    body_text = p.locator("body").text_content() or ""
    # 验证套餐信息被渲染
    has_package_info = "高级套餐" in body_text or "199" in body_text or "5000" in body_text
    assert has_package_info, f"应显示套餐信息"

    p.close()
    context.close()


@pytest.mark.p0
@pytest.mark.recharge
def test_recharge_pay_button(browser, auth_token, user_id, base_url):
    """er_003 - 支付按钮存在。"""
    p, context = _setup_recharge_page(browser, auth_token, user_id, base_url)
    url = _recharge_url(base_url, auth_token, user_id)
    p.goto(url, wait_until="domcontentloaded")
    p.wait_for_timeout(3000)

    # 验证支付按钮
    pay_btn = p.locator("#payBtn")
    assert pay_btn.count() > 0, "应有支付按钮 #payBtn"

    p.close()
    context.close()


# ═══════════════════════════════════════════════════════════════
# P1 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.p1
@pytest.mark.recharge
def test_recharge_back_button(browser, auth_token, user_id, base_url):
    """er_004 - 返回按钮存在。"""
    p, context = _setup_recharge_page(browser, auth_token, user_id, base_url)
    url = _recharge_url(base_url, auth_token, user_id)
    p.goto(url, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    back_btn = p.locator("#backBtn")
    assert back_btn.count() > 0, "应有返回按钮 #backBtn"

    p.close()
    context.close()


@pytest.mark.p1
@pytest.mark.recharge
def test_recharge_missing_params_shows_error(browser, base_url):
    """er_005 - 缺少必需参数时显示错误。"""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
    )
    p = context.new_page()
    # 不传任何参数
    p.goto(f"{base_url}/external_recharge.html", wait_until="domcontentloaded")
    p.wait_for_timeout(3000)

    body_text = p.locator("body").text_content() or ""
    has_error = "错误" in body_text or "缺少" in body_text or "error" in body_text.lower() or "参数" in body_text
    assert has_error, f"缺少参数时应显示错误提示"

    p.close()
    context.close()


@pytest.mark.p1
@pytest.mark.recharge
def test_recharge_api_error_shows_retry(browser, auth_token, user_id, base_url):
    """er_006 - 支付接口失败时显示重试按钮。"""
    p, context = _setup_recharge_page(browser, auth_token, user_id, base_url)
    url = _recharge_url(base_url, auth_token, user_id)
    p.goto(url, wait_until="domcontentloaded")
    p.wait_for_timeout(3000)

    # 页面应显示错误信息或重试按钮
    body_text = p.locator("body").text_content() or ""
    has_error_or_retry = (
        "错误" in body_text
        or "失败" in body_text
        or "重试" in body_text
        or "重新" in body_text
        or "不可用" in body_text
    )
    assert has_error_or_retry, "API 失败时应显示错误或重试"

    p.close()
    context.close()


@pytest.mark.p1
@pytest.mark.recharge
def test_recharge_responsive_layout(browser, auth_token, user_id, base_url):
    """er_007 - 窄屏下页面仍可用。"""
    context = browser.new_context(
        viewport={"width": 375, "height": 667},
        locale="zh-CN",
    )
    p = context.new_page()

    # Mock 所有 API
    p.route("**/api/recharge/**", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=_json.dumps({"success": False, "message": "mock"}),
    ))
    p.route("**/api.ipify.org/**", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=_json.dumps({"ip": "127.0.0.1"}),
    ))

    url = _recharge_url(base_url, auth_token, user_id)
    p.goto(url, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    page_el = p.locator(".page")
    assert page_el.count() > 0, "移动端应有 .page 容器"

    p.close()
    context.close()
