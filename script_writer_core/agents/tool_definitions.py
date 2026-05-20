"""
共享工具定义
统一 ask_user、load_sop 等跨 Agent 工具的定义，避免重复维护
"""

# ask_user 工具定义 - 供 ExpertAgent 和 PMAgent 共用
ASK_USER_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": "向用户提问并等待回答。必须提供 options 选项列表供用户快速选择。注意：前端会自动在选项列表末尾追加'其他'按钮供用户自由输入，你无需在 options 中手动添加'其他'选项。",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "要提问的问题内容。例如：'你喜欢什么类型的故事？'"
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "选项列表，至少提供一个选项。例如：['科幻', '悬疑', '爱情', '冒险']。无需手动添加'其他'选项，前端会自动追加。"
                },
                "context": {
                    "type": "object",
                    "description": "额外的上下文信息（可选）。例如：{'type': 'genre_selection', 'related_field': 'story_type'}"
                }
            },
            "required": ["question", "options"]
        }
    }
}

# load_sop 工具定义 - 供 PMAgent 加载 SOP 流程内容
LOAD_SOP_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "load_sop",
        "description": "加载指定 SOP（标准操作流程）的完整内容。调用后会返回该 SOP 的详细步骤、所需工具和执行指南。",
        "parameters": {
            "type": "object",
            "properties": {
                "sop_name": {
                    "type": "string",
                    "description": "SOP 名称，例如：'sop-image-generation'（图片生成流程）、'sop-video-generation'（视频生成流程）"
                }
            },
            "required": ["sop_name"]
        }
    }
}
