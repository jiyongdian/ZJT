# 剧本节点语言联动功能

## 更新内容
- 版本：2026-06-09
- 说明：剧本节点的"输出语言"选项与右上角界面语言切换器联动，当用户切换界面语言时，剧本节点的输出语言会自动同步更新。

## 功能说明

### 联动规则

| 界面语言 | 剧本输出语言 |
|----------|-------------|
| 中文 (zh-CN) | 中文（默认）- 空值 |
| English (en) | English |

### 交互行为

1. 用户点击右上角语言切换器选择"English"
2. 界面语言切换为英文
3. 剧本节点的"输出语言"下拉框自动切换为"English"
4. 节点数据 `node.data.language` 同步更新为 `"English"`

5. 用户点击右上角语言切换器选择"中文"
6. 界面语言切换为中文
7. 剧本节点的"输出语言"下拉框自动切换为"中文（默认）"
8. 节点数据 `node.data.language` 同步更新为 `""`

### 技术实现

#### 相关文件

| 文件 | 说明 |
|------|------|
| `web/js/nodes.js` | 剧本节点定义，包含语言联动逻辑 |
| `web/i18n/i18n-core.js` | i18n 核心模块，提供 `locale-changed` 事件 |
| `web/i18n/i18n-switcher.js` | 语言切换器 UI 组件 |

#### 实现代码

在剧本节点的语言选择监听部分，添加了对 `locale-changed` 事件的监听：

```javascript
// 监听右上角语言切换，联动更新剧本输出语言
if(window.ZJTi18n) {
  window.ZJTi18n.on('locale-changed', ({ locale }) => {
    // 根据界面语言自动设置剧本输出语言
    const localeToLanguage = {
      'en': 'English',
      'zh-CN': ''
    };
    const newLanguage = localeToLanguage[locale];
    if(newLanguage !== undefined) {
      // 更新节点数据
      node.data.language = newLanguage;
      // 更新下拉框显示
      const presetValues = ['', 'English', 'Deutsch', 'Français', 'Русский'];
      if(presetValues.includes(newLanguage)) {
        languageSelectEl.value = newLanguage;
        languageCustomEl.style.display = 'none';
      } else {
        languageSelectEl.value = '__custom__';
        languageCustomEl.style.display = 'block';
        languageCustomEl.value = newLanguage;
      }
    }
  });
}
```

#### 事件机制

- `ZJTi18n.on('locale-changed', callback)` - 监听语言变化事件
- 事件参数 `{ locale }` - 新的语言代码（如 `'en'`, `'zh-CN'`）

### 注意事项

1. 联动仅在用户切换界面语言时触发，不会覆盖用户手动选择的自定义语言
2. 如果用户手动选择了非预设语言（如"Deutsch"），切换界面语言后会被覆盖为对应的语言
3. 语言映射表 `localeToLanguage` 可以根据需要扩展，支持更多语言的联动
