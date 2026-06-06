---
name: sop-continue-script
description: 续写剧本工作流，在已有剧本基础上续写新集数，包括大纲补全、续集编写、合规检查、补充新角色/场景/道具、形象生成和资产就绪检查。
---

# 续写剧本工作流

## 适用场景
用户需要在已有剧本基础上续写新集数，可能需要补充新角色、新场景和新道具。

## 流程图

```
剧本架构师（环境分析+需求收集）
    ↓
判断大纲是否完整
    ↓
    ├─ 不完整 → plot-analyzer（补全大纲）
    └─ 完整 → 跳过
    ↓
story-writer（编写续集内容）
    ↓
用户确认续集剧本 ← ─┐
    ↓              │
    ├─ 满意 → 继续   │
    └─ 不满意 → 重新调用 story-writer ──┘
    ↓
content-compliance-checker（剧本检查）← ─┐
    ↓                                    │
    ├─ 通过 → 继续                        │
    └─ 不通过 → 返回 story-writer 修改 ──┘
    （最多循环3次）
    ↓
character-creator（补充新角色）
    ↓
用户确认角色卡 ← ─┐
    ↓              │
    ├─ 满意 → 选择需要生成形象的角色 → 继续 │
    └─ 不满意 → 重新调用 character-creator ──┘
    ↓
character-image-designer（生成选定角色形象）
    ↓
location-creator（补充新场景和道具）
    ↓
用户确认场景和道具 ← ─┐
    ↓                  │
    ├─ 满意 → 选择需要生成形象的场景和道具 → 继续 │
    └─ 不满意 → 重新调用 location-creator ──┘
    ↓
location-prop-image-designer（生成选定场景道具形象）
    ↓
asset-readiness-checker（资产就绪检查）
```

## 进度显示

```
【续写剧本进度】
✅ 感知环境
✅ 收集需求
✅ 需求分流
🔄 检查/补全大纲
⏳ 编写续集剧本
⏳ 确认续集剧本
⏳ 合规检查
⏳ 补充新角色
⏳ 确认角色卡
⏳ 角色形象设计
⏳ 补充新场景道具
⏳ 确认场景道具
⏳ 场景道具形象设计
⏳ 资产就绪检查
```

## 详细步骤

1. **检查大纲完整性**
   - 使用 `get_outline()` 或类似工具检查
   - 如果大纲不完整 → 调用 plot-analyzer 补全
   - 如果大纲完整 → 跳过此步骤

2. **调用 story-writer（编写续集内容）**
   - 任务：根据已有剧本和大纲编写续集
   - 输入：已有剧本、大纲、用户需求
   - 输出：续集剧本文件（JSON格式）

2.5. **用户确认续集剧本（关键步骤）**
   - **必须执行**：向用户展示生成的续集剧本，并询问是否满意
   - **展示内容**：
     - 使用 `list_scripts()` 和 `get_script()` 获取生成的续集剧本内容
     - 展示续集的关键信息：新增集数、每集梗概或部分内容
   - **询问用户**：
     - 先向用户展示续集剧本摘要或部分内容，然后调用：
     ```
     ask_user(
       question: "【续集剧本已生成】\n\n<展示续集剧本摘要或部分内容>\n\n请问您对这个续集剧本是否满意？",
       options: ["满意，继续", "不满意，需要修改"]
     )
     ```
   - **处理用户反馈**：
     - **如果用户选择"满意，继续"**：继续步骤3（调用 content-compliance-checker）
     - **如果用户选择"不满意，需要修改"**：
       1. 用户会在自由输入中说明修改意见
       2. 重新调用 story-writer，并在 `task_description` 中明确说明用户的修改要求
       3. 返回本步骤重新确认续集剧本
   - **注意事项**：
     - 必须等待用户明确回复后才能继续
     - 不要假设用户满意，必须得到明确确认
     - 如果用户提出修改意见，要完整传递给 story-writer

3. **调用 content-compliance-checker（循环检查）**
   - **第一步：调用 content-compliance-checker 进行审核**
     ```
     call_agent(
       AgentName: "content-compliance-checker",
       task_description: "请审核续集剧本的合规性和质量，检查是否包含违规内容、角色一致性、大纲一致性以及每集末尾的钩子设计"
     )
     ```

   - 任务：检查续集剧本的合规性和质量
   - 检查项同工作流A

   - **检查完成后的处理流程**：
     a. 使用 `get_script_problem(limit=200)` 获取审核结果
     b. 检查返回的 `verdict` 字段：
        - `verdict: true` → 剧本通过，继续下一步
        - `verdict: false` → 剧本有问题，需要修改

   - **如果不通过（verdict: false）**：
     - 使用 `get_script_problem()` 获取完整审核结果，提取 `problem` 字段的内容
     - 调用 story-writer 修改剧本，**必须**使用 `conversation_history` 参数传递问题：
       ```
       call_agent(
         AgentName: "story-writer",
         task_description: "请根据审核报告修改续集剧本，解决发现的问题",
         conversation_history: [
           {
             "role": "user",
             "content": <直接将 get_script_problem 返回的 problem 字段内容放在这里>
           }
         ]
       )
       ```
     - 最多循环3次

   - **如果通过或达到最大次数**：继续下一步

4. **调用 character-creator（补充新角色）**
   - ⚠️ **执行要求**：必须立即调用 `call_agent(AgentName: "character-creator", ...)`，不要只说"正在执行"
   - 任务：为续集中的新角色创建角色卡
   - 输入：续集剧本内容
   - 输出：新角色JSON文件

4.3. **用户确认角色卡（关键步骤）**
   - **必须执行**：向用户展示创建的角色卡，并询问是否满意
   - **展示内容**：
     - 使用 `list_characters()` 获取所有角色列表（包括新角色和已有角色）
     - 使用 `read_character_json(name="角色名", limit=500)` 获取每个新角色的详细信息
     - **检查形象**：检查返回JSON中的 `reference_image` 字段，判断是否已存在形象
     - 清晰展示每个新角色的关键信息：姓名、性格、背景、关系网等，以及是否已有形象
   - **询问用户（两步确认）**：

     **第一步：确认角色卡是否满意**
     - 先向用户展示所有角色的详细信息（新增角色详情 + 已有角色列表），然后调用：
     ```
     ask_user(
       question: "【角色卡已创建/更新】\n\n新增角色：\n<展示所有新角色的详细信息>\n\n已有角色：\n<列出已有角色名称>\n\n💰 算力消耗说明：\n一共有[N]个角色（新增[X]个，已有[Y]个）。\n其中[M]个角色未生成形象。\n\n请问您对这些角色卡是否满意？",
       options: ["满意，继续", "不满意，需要修改"]
     )
     ```
     - 如果用户选择"不满意，需要修改"：收集修改意见，重新调用 character-creator，返回本步骤
     - 如果用户选择"满意，继续"：进入第二步

     **第二步：选择需要生成形象的角色**
     - **过滤规则**：只列出 `reference_image` 为空的角色（未生成形象的），已有形象的角色不列入选项（除非用户主动要求重新生成）
     ```
     ask_user(
       question: "以下角色尚未生成形象，请选择需要生成的（可多选）：",
       options: ["全部生成", "角色A（新）", "角色B（已有）", ...],  // 仅列出未生成形象的角色名，动态生成
       multiSelect: true
     )
     ```
     - 记录用户选择的角色列表
     - 继续步骤4.5（调用 character-image-designer）
   - **注意事项**：
     - 必须等待用户明确回复后才能继续
     - 不要假设用户满意，必须得到明确确认
     - 用户可以选择为新角色和已有角色生成形象

4.5. **调用 character-image-designer**
   - 任务：为用户选择的角色生成形象设计图
   - 输入：角色JSON文件和用户选择的角色列表
   - 输出：角色参考图像
   - **注意**：角色形象设计完成后，character-image-designer 会同步检查并为缺少音色（`default_voice`）的角色生成参考音频，无需额外调用其他 agent 处理音色
   - 说明：根据用户在步骤4.3中的选择，为指定角色批量生成角色形象设计
   - **生成方式**：使用4宫格批量生成（每次4个角色），自动切分后保存
   - **任务描述**：
     ```
     call_agent(
       AgentName: "character-image-designer",
       task_description: "请为以下角色生成形象设计图：[用户选择的角色列表]。

       要求：
       1. 使用4宫格批量生成方式（详见character-image-designer技能说明）
       2. 只为用户指定的角色生成图像
       3. 生成anime character design reference sheet风格的角色设计图
       4. 确保角色形象与角色卡描述一致"
     )
     ```
   - ⚠️ **完成后不要说"正在执行：调用 location-creator"**，直接进入步骤5立即调用

5. **调用 location-creator（补充新场景和道具）**
   - ⚠️ **执行要求**：必须立即调用 `call_agent(AgentName: "location-creator", ...)`，不要只说"正在执行"
   - 任务：创建续集中的新场景和道具
   - 输入：续集剧本内容
   - 输出：新场景和道具JSON文件

5.3. **用户确认场景和道具（关键步骤）**
   - **必须执行**：向用户展示创建的场景和道具，并询问是否满意
   - **展示内容**：
     - 使用 `list_locations()` 获取所有场景列表（包括新场景和已有场景）
     - 使用 `list_props()` 获取所有道具列表（包括新道具和已有道具）
     - 使用 `read_location_json(name="场景名", limit=500)` 和 `read_prop_json(name="道具名", limit=500)` 获取新场景和道具的详细信息
     - **检查形象**：检查返回JSON中的 `reference_image` 字段，判断是否已存在形象
     - 清晰展示每个新场景和道具的关键信息：名称、描述、用途等，以及是否已有形象
   - **询问用户（两步确认）**：

     **第一步：确认场景和道具是否满意**
     - 先向用户展示所有场景和道具的详细信息，然后调用：
     ```
     ask_user(
       question: "【场景和道具已创建/更新】\n\n新增场景：\n<展示所有新场景的详细信息>\n\n新增道具：\n<展示所有新道具的详细信息>\n\n已有场景：<列出名称>\n已有道具：<列出名称>\n\n💰 算力消耗说明：\n一共有[M]个场景和[N]个道具。\n其中[m]个场景未生成形象，[n]个道具未生成形象。\n总计需要[场景+道具算力]算力。\n\n请问您对这些场景和道具是否满意？",
       options: ["满意，继续", "不满意，需要修改"]
     )
     ```
     - 如果用户选择"不满意，需要修改"：收集修改意见，重新调用 location-creator，返回本步骤
     - 如果用户选择"满意，继续"：进入第二步

     **第二步：选择需要生成形象的场景和道具**
     - **过滤规则**：只列出 `reference_image` 为空的场景和道具（未生成形象的），已有形象的不列入选项（除非用户主动要求重新生成）
     ```
     ask_user(
       question: "以下场景和道具尚未生成形象，请选择需要生成的（可多选）：",
       options: ["全部生成", "场景A（新）", "场景B（已有）", ..., "道具X（新）", "道具Y（已有）", ...],  // 仅列出未生成形象的项目，动态生成
       multiSelect: true
     )
     ```
     - 记录用户选择的场景和道具列表
     - 继续步骤5.5（调用 location-prop-image-designer）
   - **注意事项**：
     - 必须等待用户明确回复后才能继续
     - 不要假设用户满意，必须得到明确确认
     - 用户可以选择为新场景道具和已有场景道具生成形象

5.5. **调用 location-prop-image-designer**
   - 任务：为用户选择的场景和道具生成形象设计图
   - 输入：场景和道具JSON文件以及用户选择的列表
   - 输出：场景和道具参考图像
   - 说明：根据用户在步骤5.3中的选择，为指定场景和道具批量生成形象设计
   - **生成方式**：使用4宫格批量生成（每次4个场景/道具），自动切分后保存
   - **任务描述**：
     ```
     call_agent(
       AgentName: "location-prop-image-designer",
       task_description: "请为以下场景和道具生成形象设计图：

       场景：[用户选择的场景列表]
       道具：[用户选择的道具列表]

       要求：
       1. 使用4宫格批量生成方式（详见location-prop-image-designer技能说明）
       2. 只为用户指定的场景和道具生成图像
       3. 为场景生成detailed location design reference sheet风格的设计图
       4. 为道具生成detailed prop design reference sheet风格的设计图
       5. 确保形象与描述一致"
     )
     ```

6. **调用 asset-readiness-checker**
   - 说明：在所有资产创建完成后，调用资产就绪检查专家进行最终检查
   - ⚠️ **执行要求**：必须立即调用，不要只说"正在执行"
   - **任务描述**：
     ```
     call_agent(
       AgentName: "asset-readiness-checker",
       task_description: "请检查当前所有资产的完备性，包括角色（reference_image 和 default_voice）、场景（reference_image）、道具（reference_image），以及世界画风（visual_style）和构图倾向（composition_preference）的合理性和精简性。同时提醒用户点击提交数据按钮。"
     )
     ```
   - 专家会生成完整的检查报告并展示给用户
   - 如果报告中有画风/构图问题，使用 `update_world()` 修正后重新检查
