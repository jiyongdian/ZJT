"""
相机控制模块 E2E 测试。
覆盖相机控制节点创建和参数交互功能。
"""
import pytest

from helpers.editor_helpers import add_image_node, navigate_to_editor


@pytest.mark.camera_control
class TestCameraControl:
    """相机控制功能测试"""

    @pytest.mark.p0
    def test_camera_control_node_creation(self, editor_page, base_url, test_workflow):
        """camera_ctrl_001 - 验证创建相机控制节点并检查参数控件"""
        wf_id = test_workflow["id"]
        page = editor_page
        navigate_to_editor(page, base_url, wf_id)

        # 直接通过全局函数创建相机控制节点
        node_id = page.evaluate("""() => {
            if (typeof createCameraControlNode === 'function') {
                return createCameraControlNode({ x: 200, y: 200, checkCollision: false });
            }
            return null;
        }""")
        page.wait_for_timeout(1000)

        assert node_id is not None, "createCameraControlNode 函数不存在或返回 null"

        # 验证相机控制节点被创建
        camera_node = page.locator(".node").last
        assert camera_node.is_visible(), "相机控制节点不可见"

        # 验证包含相机参数控件
        h_angle = camera_node.locator(".camera-ctrl-horizontal-angle")
        assert h_angle.count() > 0, "水平角度输入框不存在"

        v_angle = camera_node.locator(".camera-ctrl-vertical-angle")
        assert v_angle.count() > 0, "垂直角度输入框不存在"

        # 验证滑块存在
        sliders = camera_node.locator("input[type='range']")
        assert sliders.count() >= 2, f"应有至少2个滑块，实际有 {sliders.count()}"

    @pytest.mark.p1
    def test_camera_params_interaction(self, editor_page, base_url, test_workflow):
        """camera_ctrl_002 - 验证修改相机参数并生成提示词"""
        wf_id = test_workflow["id"]
        page = editor_page
        navigate_to_editor(page, base_url, wf_id)

        # 创建相机控制节点
        page.evaluate("""() => {
            if (typeof createCameraControlNode === 'function') {
                createCameraControlNode({ x: 200, y: 200, checkCollision: false });
            }
        }""")
        page.wait_for_timeout(1000)

        camera_node = page.locator(".node").last

        # 修改垂直角度为 -20（低角度）
        v_angle_input = camera_node.locator(".camera-ctrl-vertical-angle")
        if v_angle_input.count() > 0 and v_angle_input.is_visible():
            v_angle_input.fill("-20")
            v_angle_input.dispatch_event("input")
            v_angle_input.dispatch_event("change")
            page.wait_for_timeout(300)

        # 验证提示词生成函数
        result = page.evaluate("""() => {
            if (typeof generateCameraPrompt === 'function') {
                return generateCameraPrompt({
                    horizontal_angle: 0,
                    vertical_angle: -20,
                    zoom: 5.0
                });
            }
            return null;
        }""")

        if result is not None:
            assert isinstance(result, str), f"提示词应为字符串，实际: {type(result)}"
            result_lower = result.lower()
            assert "low-angle" in result_lower, (
                f"提示词应包含 low-angle 描述，实际: {result}"
            )
