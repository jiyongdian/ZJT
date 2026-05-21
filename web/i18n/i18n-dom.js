/**
 * ZJT i18n DOM 扫描器
 *
 * 功能：
 * - 扫描 HTML 中的 data-i18n 属性，自动翻译
 * - 支持 placeholder, title, innerHTML 等属性
 * - 支持嵌套元素重新翻译（如工作流重载时）
 */

window.ZJTi18nDOM = (() => {
  const i18n = window.ZJTi18n;

  /**
   * 扫描 DOM 中的 data-i18n 属性并翻译
   * @param {Element} root - 扫描的根元素（默认为 document）
   */
  function scanDOM(root = document) {
    // 查找所有带有 data-i18n 属性的元素
    const elements = root.querySelectorAll('[data-i18n]');

    elements.forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (!key) return;

      // 支持多个目标属性，用逗号分隔
      // 格式：'key:attr1,attr2' 或 'key:text' 或简写 'key'（默认为 text）
      let targets = 'text'; // 默认目标
      let translationKey = key;

      if (key.includes(':')) {
        const [k, t] = key.split(':');
        translationKey = k;
        targets = t;
      }

      const translated = i18n.t(translationKey);

      // 处理多个目标属性
      targets.split(',').forEach((target) => {
        target = target.trim();

        if (target === 'text') {
          el.textContent = translated;
        } else if (target === 'html') {
          el.innerHTML = translated;
        } else if (target === 'placeholder') {
          el.placeholder = translated;
        } else if (target === 'title') {
          el.title = translated;
        } else if (target === 'value') {
          el.value = translated;
        } else {
          // 其他自定义属性
          el.setAttribute(target, translated);
        }
      });
    });
  }

  /**
   * 设置语言并重新扫描 DOM
   * @param {string} locale - 语言代码
   * @param {Array<string>} namespaces - 需要加载的命名空间
   * @param {Element} root - 需要重新扫描的根元素
   */
  async function setLocale(locale, namespaces = ['common'], root = document) {
    await i18n.setLocale(locale, namespaces);
    scanDOM(root);
  }

  // 初始化：在语言变化时自动重扫 DOM
  i18n.on('locale-changed', () => {
    scanDOM(document);
  });

  return {
    scanDOM,
    setLocale
  };
})();
