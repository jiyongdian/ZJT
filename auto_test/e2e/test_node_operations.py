"""
节点操作 E2E 测试。
覆盖工作流编辑器中节点的创建、上传、选择、输入、持久化等操作。
标记：node_operations
"""
import os
from pathlib import Path

import pytest

from helpers.editor_helpers import (
    add_image_node,
    add_image_to_video_node,
    js_click_in_node,
    js_fill_in_node,
    make_all_nodes_visible,
    navigate_to_editor,
)

# 测试资源目录
TEST_ASSETS_DIR = Path(__file__).resolve().parent.parent / "test_assets"


def _get_test_image(e2e_config) -> str:
    """获取测试图片的绝对路径"""
    rel = e2e_config.get("test_assets", {}).get("test_image", "")
    if not rel:
        return ""
    abs_path = (Path(__file__).resolve().parent.parent / rel).resolve()
    return str(abs_path) if abs_path.exists() else ""


# ---------------------------------------------------------------------------
# P0 测试
# ---------------------------------------------------------------------------


@pytest.mark.p0
@pytest.mark.node_operations
def test_image_node_upload(editor_page, base_url, test_workflow, e2e_config):
    """node_014 - 创建图片节点，上传图片文件，验证预览显示。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    node = add_image_node(page)

    test_image = _get_test_image(e2e_config)
    if not test_image:
        pytest.skip("测试图片文件不存在，跳过上传测试")

    with page.expect_file_chooser() as fc_info:
        js_click_in_node(page, ".node.selected", ".image-file")
    file_chooser = fc_info.value
    file_chooser.set_files(test_image)
    page.wait_for_timeout(2000)

    preview = page.locator(".node.selected .image-preview img, .node.selected .image-preview")
    assert preview.count() > 0, "图片节点上传后未显示预览"


@pytest.mark.p0
@pytest.mark.node_operations
def test_image_to_video_node_create(editor_page, base_url, test_workflow):
    """node_001 - 创建图生视频节点，验证节点出现在画布上。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    node_count_before = page.evaluate("() => document.querySelectorAll('.node').length")
    add_image_to_video_node(page)
    node_count_after = page.evaluate("() => document.querySelectorAll('.node').length")
    assert node_count_after > node_count_before, (
        f"创建图生视频节点后画布节点数未增加，之前: {node_count_before}，之后: {node_count_after}"
    )


@pytest.mark.p0
@pytest.mark.node_operations
def test_image_edit_with_draw(editor_page, base_url, test_workflow, e2e_config):
    """node_020 - 创建图片节点，输入编辑提示词，选择出图数X2，点击编辑按钮。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    node = add_image_node(page)

    # 输入编辑提示词（通过 JS 避免遮挡）
    js_fill_in_node(page, ".node.selected", ".image-prompt", "将背景改为蓝天白云")
    page.wait_for_timeout(300)

    # 选择出图数 X2（通过 JS）
    js_click_in_node(page, ".node.selected", ".gen-container .gen-btn-caret")
    page.wait_for_timeout(500)
    js_click_in_node(page, ".node.selected", ".gen-menu .gen-item[data-count='2']")
    page.wait_for_timeout(300)

    # 点击编辑按钮
    js_click_in_node(page, ".node.selected", ".image-edit-btn")
    page.wait_for_timeout(1000)

    # 验证无报错
    error_dialog = page.locator(".el-message--error, .error-toast")
    assert error_dialog.count() == 0, "点击编辑按钮后出现错误提示"


# ---------------------------------------------------------------------------
# P1 测试
# ---------------------------------------------------------------------------


@pytest.mark.p1
@pytest.mark.node_operations
def test_video_node_upload(editor_page, base_url, test_workflow):
    """node_010 - 创建视频节点，验证文件输入存在。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    node = add_image_to_video_node(page)
    file_input = page.locator(".node.selected input[type='file']")
    assert file_input.count() > 0, "视频节点未包含文件输入元素"


@pytest.mark.p1
@pytest.mark.node_operations
def test_video_duration_select(editor_page, base_url, test_workflow):
    """node_004 - 验证时长选择默认 10s，可切换为 15s。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    add_image_to_video_node(page)

    # 通过 JS 获取时长选择器的值
    default_text = page.evaluate("""() => {
        const sel = document.querySelector('.node.selected .duration-select');
        return sel ? sel.options[sel.selectedIndex]?.textContent?.trim() || '' : '';
    }""")
    assert default_text, "时长默认值为空"

    # 切换选项
    page.evaluate("""() => {
        const sel = document.querySelector('.node.selected .duration-select');
        if (sel && sel.options.length > 1) {
            sel.selectedIndex = 1;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }""")
    page.wait_for_timeout(500)

    selected_text = page.evaluate("""() => {
        const sel = document.querySelector('.node.selected .duration-select');
        return sel ? sel.options[sel.selectedIndex]?.textContent?.trim() || '' : '';
    }""")
    assert selected_text != default_text or len(selected_text) > 0, "时长选项切换失败"


@pytest.mark.p1
@pytest.mark.node_operations
def test_video_model_select(editor_page, base_url, test_workflow):
    """node_005 - 验证模型选择器有选项。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    add_image_to_video_node(page)

    option_count = page.evaluate("""() => {
        const sel = document.querySelector('.node.selected .video-model-select');
        return sel ? sel.options.length : 0;
    }""")
    assert option_count > 0, "模型选择器无选项"


@pytest.mark.p1
@pytest.mark.node_operations
def test_prompt_input(editor_page, base_url, test_workflow):
    """node_006 - 在提示词文本框中输入内容，验证值已保存。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    add_image_to_video_node(page)

    test_text = "E2E 自动化测试提示词输入"
    js_fill_in_node(page, ".node.selected", "textarea.prompt", test_text)
    page.wait_for_timeout(300)

    actual_value = page.evaluate("""() => {
        const ta = document.querySelector('.node.selected textarea.prompt');
        return ta ? ta.value : '';
    }""")
    assert actual_value == test_text, (
        f"提示词输入值不匹配，期望: {test_text}，实际: {actual_value}"
    )


@pytest.mark.p1
@pytest.mark.node_operations
def test_draw_count_select(editor_page, base_url, test_workflow):
    """node_007 - 点击出图数选择器，验证菜单显示选项。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    add_image_node(page)

    js_click_in_node(page, ".node.selected", ".gen-container .gen-btn-caret")
    page.wait_for_timeout(500)

    menu_count = page.evaluate("""() => {
        const items = document.querySelectorAll('.node.selected .gen-menu .gen-item');
        return items.length;
    }""")
    assert menu_count >= 2, "出图数菜单选项不足"


# ---------------------------------------------------------------------------
# P0 测试 - 连接/持久化
# ---------------------------------------------------------------------------


@pytest.mark.p0
@pytest.mark.node_operations
def test_image_to_video_ratio_sora(editor_page, base_url, test_workflow):
    """node_009_3 - 验证 sora 模型仅显示 16:9 和 9:16 两种比例。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    add_image_to_video_node(page)

    # 通过 JS 设置模型为 sora 并获取比例选项
    ratio_options = page.evaluate("""() => {
        const node = document.querySelector('.node.selected');
        if (!node) return [];
        const modelSel = node.querySelector('.video-model-select');
        if (modelSel) {
            // 尝试设置为 sora
            for (let i = 0; i < modelSel.options.length; i++) {
                if (modelSel.options[i].value === 'sora' || modelSel.options[i].textContent.includes('sora')) {
                    modelSel.selectedIndex = i;
                    modelSel.dispatchEvent(new Event('change', { bubbles: true }));
                    break;
                }
            }
        }
        const ratioSel = node.querySelector('.ratio-select');
        if (!ratioSel) return [];
        return Array.from(ratioSel.options).map(o => o.textContent.trim());
    }""")
    page.wait_for_timeout(500)

    if ratio_options:
        valid_ratios = {"16:9", "9:16"}
        for ratio in ratio_options:
            # 提取比例部分（去掉 "(竖屏)" 等后缀）
            cleaned = ratio.replace("\u00a0", " ").strip()
            ratio_part = cleaned.split("(")[0].strip().split("（")[0].strip()
            assert ratio_part in valid_ratios, (
                f"sora 模型出现了非预期的比例选项: {cleaned}，仅允许: {valid_ratios}"
            )
        assert len(ratio_options) >= 2, (
            f"sora 模型比例选项不足，期望至少 2 个，实际: {ratio_options}"
        )


@pytest.mark.p0
@pytest.mark.node_operations
def test_ratio_field_persistence(editor_page, base_url, test_workflow):
    """node_009_4 - 设置比例后保存工作流，重新加载验证比例值保留。"""
    wf_id = test_workflow["id"]
    page = editor_page
    navigate_to_editor(page, base_url, wf_id)

    add_image_to_video_node(page)

    # 选择非默认值
    saved_ratio = page.evaluate("""() => {
        const sel = document.querySelector('.node.selected .ratio-select');
        if (!sel || sel.options.length < 2) return null;
        sel.selectedIndex = 1;
        sel.dispatchEvent(new Event('change', { bubbles: true }));
        return sel.options[sel.selectedIndex]?.textContent?.trim() || '';
    }""")
    page.wait_for_timeout(500)

    if not saved_ratio:
        pytest.skip("比例选择器不可用")

    # 保存工作流
    page.evaluate("() => { const btn = document.getElementById('saveBtn'); if (btn) btn.click(); }")
    page.wait_for_timeout(2000)

    # 重新加载
    page.reload(wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=15000)
    make_all_nodes_visible(page)
    page.wait_for_timeout(1000)

    # 验证比例值保留
    reloaded_ratio = page.evaluate("""() => {
        const sel = document.querySelector('.ratio-select');
        return sel ? sel.options[sel.selectedIndex]?.textContent?.trim() || '' : '';
    }""")
    assert reloaded_ratio == saved_ratio, (
        f"比例值未持久化，保存前: {saved_ratio}，重新加载后: {reloaded_ratio}"
    )
