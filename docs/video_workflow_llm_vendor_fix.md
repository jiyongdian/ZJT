# Video Workflow 剧本节点 LLM 供应商修复指南

## 概述

本文档介绍了针对 video_workflow 剧本节点的两个改进：

1. **显示 LLM 供应商信息** - 模型按供应商分组，显示图标和名称
2. **修复模型路由** - 确保选择的 zjt_api qwen3.5 真的调用 zjt_api（而不是 aliyun）

---

## 改动总结

### 前端改动 (web/js/nodes.js)

#### 改动 1: 显示供应商信息
```javascript
// 拆分模型选项现在按供应商分组显示
// 例如：
//   ☁️ jiekou (供应商分组)
//     - gemini-3-flash-preview
//   🌐 aliyun (供应商分组)
//     - qwen3.5-plus
//   🚀 zjt_api (供应商分组)
//     - qwen3.5-plus

// 每个选项都保存了供应商信息到 dataset
option.dataset.vendorId = model.vendor_id
option.dataset.vendorName = model.vendor_name
option.dataset.supportsThinking = model.supports_thinking
option.dataset.contextWindow = model.context_window
```

#### 改动 2: 发送 vendor_id 给后端
```javascript
// 调用 /api/parse-script 时现在发送 vendor_id
body: JSON.stringify({
  script_content: node.data.scriptContent,
  model: node.data.splitModel,
  model_id: node.data.splitModelId,
  vendor_id: node.data.splitModelVendorId,  // 新增！
  // ... 其他参数
})
```

### 后端改动 (server.py)

```python
# /api/parse-script 端点现在接收 vendor_id
vendor_id = body.get('vendor_id', None)

# 优先使用前端发送的 vendor_id
if vendor_id:
    real_vendor_id = int(vendor_id)
# 其次才根据 model_id 查询（避免误路由）
if real_vendor_id == 1 and model_id:
    real_vendor_id = VendorModelModel.get_vendor_id_by_model_id(int(model_id))
```

---

## 快速验证清单

### ✅ 检查 1: 前端界面
```
□ 打开 video_workflow.html
□ 创建剧本节点
□ 点击"拆分模型"下拉框
□ 验证模型按供应商分组显示（看到 optgroup）
□ 验证每组标题有图标（如 ☁️, 🌐, 🚀）
□ 验证同一模型可能在多个供应商下出现（如 qwen3.5）
```

### ✅ 检查 2: 模型选择
```
□ 在下拉框中选择 "qwen3.5"
  （应该在 "🚀 zjt_api" 分组下，不是 "🌐 aliyun" 分组下）
□ 打开浏览器开发者工具 (F12) → Console
□ 查找日志输出，应该看到：
  "[剧本节点] 拆分模型切换为: qwen3.5, modelId: ..., vendor: zjt_api"
□ 验证 vendor 信息正确
```

### ✅ 检查 3: 实际调用
```
□ 在剧本节点输入一些剧本内容
□ 点击"拆分镜组"按钮
□ 查看后端日志，应该看到：
  ✅ "zjt_api API request" 或类似日志（不是 aliyun）
  ❌ 不应该出现 "aliyun API key invalid" 错误
□ 剧本应该成功解析
```

---

## 故障排查

### 问题 1: 下拉框不显示分组 (optgroup)

**可能原因**：浏览器缓存或 JavaScript 加载问题

**解决方案**：
```bash
# 清除浏览器缓存
# 或在浏览器 DevTools 中：
localStorage.clear()
sessionStorage.clear()
# 然后刷新页面 (Ctrl+F5)
```

### 问题 2: 选择了 zjt_api 但仍然调用 aliyun

**可能原因**：
- vendor_id 没有正确保存到 node.data
- 后端没有收到 vendor_id 参数

**排查步骤**：
```javascript
// 在浏览器 Console 中运行
// 查看前端保存的数据
console.log(node.data.splitModelVendorId)
console.log(node.data.splitModelVendorName)

// 应该输出：
// 6 (或其他非1的ID)
// "zjt_api"
```

```bash
# 在后端日志中查看
grep -i "vendor_id" server.log
# 应该看到类似：
# real_vendor_id = 6
# 而不是回退到默认值 1
```

### 问题 3: model_id 为空

**可能原因**：前端没有收到 /api/models 返回的 model_id

**排查步骤**：
```javascript
// 在浏览器 Console 中运行
// 检查模型数据是否正确加载
console.log(window._scriptSplitModels)
// 应该看到模型列表，每个都有 model_id 字段
```

---

## 数据流图

```
前端界面
  ↓
用户在下拉框中选择 "qwen3.5" (zjt_api 供应商)
  ↓
node.data 更新:
  - splitModel = "qwen3.5"
  - splitModelId = 5
  - splitModelVendorId = 6  ← 关键！
  - splitModelVendorName = "zjt_api"
  ↓
用户点击"拆分镜组"
  ↓
前端发送 /api/parse-script 请求:
  {
    model: "qwen3.5",
    model_id: 5,
    vendor_id: 6,  ← 关键参数！
    ...
  }
  ↓
后端接收
  ↓
vendor_id = 6 (优先使用，不查询数据库)
  ↓
调用 get_llm_client("qwen3.5", vendor_id=6)
  ↓
LLMClientFactory.get_client() 根据 vendor_id=6 查询数据库
  ↓
获得 vendor_name = "zjt_api"
  ↓
返回 ZJT API 客户端 (get_zjt_openai_client())
  ↓
✅ 正确调用 ZJT API
  ↓
剧本解析完成，返回结果给前端
```

---

## API 参考

### /api/vendors (已有)

返回所有供应商及其图标：

```json
{
  "success": true,
  "vendors": [
    {
      "id": 1,
      "vendor_name": "jiekou",
      "icon": "☁️"
    },
    {
      "id": 2,
      "vendor_name": "aliyun",
      "icon": "🌐"
    },
    {
      "id": 6,
      "vendor_name": "zjt_api",
      "icon": "🚀"
    }
  ]
}
```

### /api/models (已有)

返回所有可用模型（已过滤无效供应商）：

```json
{
  "success": true,
  "models": [
    {
      "id": "qwen3.5",
      "model_id": 5,
      "name": "qwen3.5-plus",
      "vendor_id": 6,
      "vendor_name": "zjt_api",
      "supports_thinking": false,
      "context_window": 131072
    },
    {
      "id": "qwen3.5",
      "model_id": 5,
      "name": "qwen3.5-plus",
      "vendor_id": 2,
      "vendor_name": "aliyun",
      "supports_thinking": false,
      "context_window": 131072
    }
  ]
}
```

### /api/parse-script (已改进)

请求体现在支持 vendor_id：

```json
{
  "script_content": "...",
  "model": "qwen3.5",
  "model_id": 5,
  "vendor_id": 6,
  "max_group_duration": 15,
  "force_medium_shot": false,
  "no_bg_music": false,
  "split_multi_dialogue": false,
  "narration_as_dialogue": false,
  "language": ""
}
```

---

## 相关文件

| 文件 | 改动 | 说明 |
|------|------|------|
| web/js/nodes.js | +73, -18 | 前端模型选择和发送 vendor_id |
| server.py | +12, -4 | 后端接收和优先使用 vendor_id |
| llm/llm_client_factory.py | 无改动 | 已支持 vendor_id 参数 |
| llm/script_parser.py | 无改动 | 已调用 get_llm_client 时传递 vendor_id |
| api/script_writer.py | 无改动 | /api/vendors 和 /api/models 已实现 |

---

## 提交信息

```
f39ca2d - 改进 video_workflow 中剧本节点的 LLM 选项展示
626429f - 修复剧本节点模型路由问题：优先使用前端选择的供应商
```

---

## 测试环境

建议测试以下场景：

1. **单供应商单模型** - Gemini 3 Flash (jiekou)
2. **多供应商同模型** - qwen3.5 (zjt_api vs aliyun) ← 最重要
3. **Ollama 本地模型** - ollama:xxxx
4. **模型切换** - 在不同供应商间快速切换

---

## 常见问题

**Q: 为什么要发送 vendor_id？**
A: 同一个模型可能在多个供应商存在（如 qwen3.5 在 zjt_api 和 aliyun），只有 vendor_id 能准确指定用户的选择。

**Q: 如果没有传递 vendor_id 会怎样？**
A: 后端会根据 model_id 查询数据库，但因为可能有多条记录，返回的可能不是用户选择的那个。因此 vendor_id 参数是必要的。

**Q: 后端是否有向后兼容？**
A: 是的。如果前端没有传递 vendor_id（旧版本客户端），后端会尝试从 model_id 查询。优先级是：vendor_id > model_id 查询 > 默认值。

---

## 反馈和改进

如发现问题或有改进建议，请提交 Issue 或 PR。
