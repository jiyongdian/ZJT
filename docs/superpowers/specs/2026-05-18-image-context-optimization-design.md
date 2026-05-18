# 图片上下文优化设计文档

## 背景

营销智能体对话中，用户上传的图片以 base64 编码注入 LLM 对话历史。多轮对话中图片 token 持续累积，导致上下文窗口耗尽。

## 方案：首轮合并描述 + 后续文字替代

### 流程

```
首轮（图片首次进入对话）:
  system prompt 追加指令 → LLM 回答时附带 <image_summary> → 提取描述 → 替换历史中的 base64

后续轮次:
  对话历史中只有文字描述 → 不再消耗图片 token → 专家智能体也使用文字描述
```

### 修改文件

#### 1. `script_writer_core/agents/pm_agent.py`

**`execute()` (L181-202)** — 有图片时追加描述指令到 system prompt:

```python
if task.image_urls:
    # 原有多模态构建逻辑不变...
    # 追加图片描述指令到 system prompt
    self._pending_image_description = True
```

在 `__init__` 中新增 `self._pending_image_description = False` 标志。

**`_run_pm_loop()` (L310-330)** — LLM 返回纯文本时提取描述并替换:

```python
# 提取 <image_summary>
if self._pending_image_description:
    summaries = self._extract_image_summaries(content)
    if summaries:
        self._replace_images_with_descriptions(summaries)
        self._pending_image_description = False
    # 清理响应文本中的 <image_summary> 标签
    content = self._clean_image_summaries(content)
```

**Expert 转发 (L533-544)** — 传文字描述而非 base64:

```python
# 替换 image_base64_list 为 image_descriptions
image_descriptions = self._image_descriptions or []
expert_task = {
    ...
    "image_descriptions": image_descriptions,
    "image_base64_list": []  # 不再传 base64
}
```

**新增方法:**

- `_extract_image_summaries(text)` — 用正则提取 `<image_summary>` 标签内容
- `_replace_images_with_descriptions(summaries)` — 遍历 history，将多模态 content（含 image_url）替换为纯文本描述
- `_clean_image_summaries(text)` — 从推送给前端的文本中移除 `<image_summary>` 标签

#### 2. `script_writer_core/agents/expert_agent.py`

**`execute_task()` (L133-151)** — 使用文字描述替代 base64:

```python
image_descriptions = task.get("image_descriptions", [])
if image_descriptions:
    # 将文字描述作为普通 user 消息注入
    desc_text = "\n".join(image_descriptions)
    self.add_to_history("user", f"[用户提供的参考图片描述]\n{desc_text}\n\n{task_description}")
elif image_urls:
    # 兜底：如果没有文字描述但有 URL，仍用原方式
    # ... 原有多模态逻辑不变
```

### 图片描述指令内容（追加到 system prompt）

```
当回复用户时，请在回复末尾用 <image_summary> 标签对用户上传的每张图片进行详细文字描述，
包括图片的主体内容、风格、色调、构图、文字信息等。格式：
<image_summary>
图片1：...
图片2：...
</image_summary>
```

### 数据流

```
前端上传图片
    ↓
PM Agent execute(): 构建 base64 多模态消息 + 追加描述指令到 system prompt
    ↓
LLM 首轮回答: 正常回答 + <image_summary>...</image_summary>
    ↓
PM 提取 image_summary → 替换 history 中的 base64 → 清理响应文本
    ↓
后续轮次: 只有文字描述，无 base64
    ↓
Expert Agent 调用: 传 image_descriptions（文字）而非 image_base64_list
```

### 不影响的场景

- `image_urls`（HTTP URL）始终保留，工具（如 edit_image）需要
- 前端展示不变，`<image_summary>` 标签在推送前清理
- 现有压缩逻辑不受影响

### 验证方式

1. 上传图片发起对话，检查日志中 image_summary 是否被正确提取
2. 检查第二轮 LLM 调用的 messages 中是否不再包含 base64
3. 检查 Expert Agent 接收到的 image_descriptions 是否为文字
4. 前端显示正常，不含 <image_summary> 标签
