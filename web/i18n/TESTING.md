# ZJT i18n 快速测试指南

## 快速验证

### 1. 验证文件结构

```bash
# 查看所有创建的 i18n 文件
find web/i18n -type f | sort

# 应该看到 13 个文件：
# - 5 个 JS/CSS 核心文件
# - 8 个翻译 JSON 文件（4 个中文 + 4 个英文）
```

### 2. 验证 server.py 改动

```bash
# 检查正则是否支持 /i18n/ 路径
grep -n "js|css|i18n" server.py

# 应该找到：
# pattern = r'(<(?:script|link)[^>]*(?:src|href)=")(/(?:js|css|i18n)/[^"]+)(")'
```

### 3. 在浏览器中测试

#### video_workflow.html
1. 打开 http://localhost:8000/video-workflow
2. 在右上角工具栏找到 🌍 语言切换器
3. 点击下拉菜单，选择 "English"
4. 验证所有中文文本变为英文：
   - "创作流程" → "Creative Process"
   - "保存" → "Save"
   - "视频比例" → "Video Ratio"
5. 刷新页面，验证语言选择被记住

#### index.html
1. 打开 http://localhost:8000/
2. 在页面头部找到 🌍 语言切换器
3. 切换语言，验证文本更新
4. 检查：
   - 按钮文本变化
   - 标题翻译

#### marketing_agent.html
1. 打开 http://localhost:8000/marketing_agent
2. 切换语言并验证

### 4. 验证 localStorage

打开浏览器开发者工具 (F12)：

```javascript
// 在控制台输入
localStorage.getItem('zjt_locale')

// 应该返回：
// "zh-CN" 或 "en"

// 修改语言后再查看，应该更新为对应值
```

### 5. 验证翻译键

```javascript
// 在控制台输入
ZJTi18n.t('save')      // 应返回 "保存" 或 "Save"
ZJTi18n.t('page_title') // 应返回对应的页面标题
ZJTi18n.getLocale()    // 应返回当前语言代码

// 尝试参数替换
ZJTi18n.t('welcome', { name: 'John' })
```

### 6. 验证响应式更新（Vue 页面）

在 index.html 或 marketing_agent.html 打开控制台：

```javascript
// 手动切换语言
ZJTi18n.setLocale('en', ['common', 'index'])

// 页面应该立即更新所有翻译，无需刷新
```

### 7. 验证工作流重载兼容（video_workflow.html）

1. 打开 video_workflow.html
2. 添加一些节点到工作流
3. 点击"保存"按钮保存工作流
4. 刷新页面重新加载
5. 验证翻译仍然正确显示

### 8. 验证缓存更新

```bash
# 修改 pyproject.toml 中的版本号
version = "0.x.x"  # 改为新版本

# 重启服务器后，在浏览器网络标签查看
# i18n-core.js 等文件应该带有新的 ?v= 版本号参数
# 这确保浏览器会获取最新的文件
```

## 常见问题排查

### 翻译未显示（显示原键）

**症状**：页面显示 "save"、"page_title" 等键而不是翻译文本

**排查步骤**：
1. 检查浏览器控制台是否有加载错误
2. 查看网络标签，翻译 JSON 文件是否正确加载
3. 检查 JSON 文件格式是否有效：`python -m json.tool web/i18n/locales/zh-CN/common.json`
4. 确保 `ZJTi18n.init()` 已调用且包含正确的命名空间

### 语言切换无反应

**症状**：点击语言切换器无反应

**排查步骤**：
1. 检查浏览器控制台是否有 JavaScript 错误
2. 确保 i18n-switcher.js 已加载
3. 在控制台手动测试：`ZJTi18nSwitcher.attachToHeader()`

### Vue 页面文本不更新

**症状**：切换语言后，Vue 模板中的文本不更新

**排查步骤**：
1. 确保已调用 `app.use(window.ZJTi18nVue)`
2. 检查模板使用的是 `$t()` 而不是 `t()`
3. 确保在 Vue 应用创建后初始化 i18n

### 页面刷新后丢失翻译

**症状**：切换语言后刷新页面，语言又变回中文

**排查步骤**：
1. 检查 localStorage 是否已保存：`localStorage.getItem('zjt_locale')`
2. 确保 `ZJTi18n.init()` 在页面加载时被调用
3. 检查浏览器是否禁用了 localStorage

## 性能测试

```javascript
// 测试首次加载时间
console.time('i18n-init')
await ZJTi18n.init(['common', 'video_workflow', 'index', 'marketing_agent'])
console.timeEnd('i18n-init')

// 测试语言切换时间
console.time('locale-switch')
await ZJTi18n.setLocale('en', ['common', 'video_workflow'])
console.timeEnd('locale-switch')

// 测试翻译函数性能
console.time('t-function')
for (let i = 0; i < 1000; i++) {
  ZJTi18n.t('save')
}
console.timeEnd('t-function')
```

## 添加新翻译的检查清单

- [ ] 为中文和英文都添加了翻译键
- [ ] JSON 格式有效（可用 `python -m json.tool` 验证）
- [ ] 使用了正确的 i18n 属性或函数：
  - HTML：`data-i18n="key"`
  - Vue 模板：`{{ $t('key') }}`
  - JavaScript：`t('key')`
- [ ] 如果是新的命名空间，已在 `init()` 中添加
- [ ] 已在多个语言版本中都添加了相同的键

## 支持的属性

HTML `data-i18n` 属性支持的值：

```html
<!-- 文本内容 -->
<div data-i18n="key">原文</div>

<!-- 多个属性 -->
<input data-i18n="key:placeholder,title" />

<!-- 支持的属性：text, html, placeholder, title, value 等 -->
<button data-i18n="save:title">
  <span data-i18n="save">保存</span>
</button>
```

## 打开/关闭 i18n 调试

```javascript
// 启用调试日志
window.i18nDebug = true

// 在 i18n-core.js 中会输出详细的加载和翻译日志

// 关闭调试
window.i18nDebug = false
```

## 下一步：添加新语言

1. 创建新语言的翻译文件：
   ```
   web/i18n/locales/ja/common.json
   web/i18n/locales/ja/video_workflow.json
   ...
   ```

2. 修改 i18n-switcher.js 中的 `languages` 数组：
   ```javascript
   const languages = [
     { code: 'zh-CN', name: '中文', nativeName: '中文' },
     { code: 'en', name: 'English', nativeName: 'English' },
     { code: 'ja', name: '日本語', nativeName: '日本語' }
   ]
   ```

3. 测试新语言切换

---

**测试时间预期**：5-10 分钟
**成功标志**：所有文本都能正确显示中英文翻译，语言切换流畅，localStorage 持久化有效
