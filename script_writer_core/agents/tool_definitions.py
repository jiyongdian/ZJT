"""
共享工具定义
统一 ask_user 等跨 Agent 工具的定义，避免重复维护
"""

# ask_user 工具定义 - 供 ExpertAgent 和 PMAgent 共用
ASK_USER_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": "向用户提问并等待回答。必须提供 options 选项列表供用户快速选择，用户也可以点击'其他'选项自由输入。",
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
                    "description": "必填的选项列表，至少提供一个选项。例如：['科幻', '悬疑', '爱情', '冒险']。用户可以选择选项，也可以点击'其他'自由输入。"
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
