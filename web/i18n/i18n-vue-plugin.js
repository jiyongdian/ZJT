/**
 * ZJT i18n Vue 3 插件
 *
 * 提供：
 * - $t() 全局方法（在模板和 JS 中使用）
 * - 自动重渲染（当语言变化时）
 */

window.ZJTi18nVue = {
  install(app, options = {}) {
    const i18n = window.ZJTi18n;
    const Vue = window.Vue;

    // 全局 $t() 方法
    app.config.globalProperties.$t = (key, params) => i18n.t(key, params);

    // 全局 $locale() 方法
    app.config.globalProperties.$locale = () => i18n.getLocale();

    // 全局 $setLocale() 方法
    app.config.globalProperties.$setLocale = (locale, namespaces) =>
      i18n.setLocale(locale, namespaces);

    // 响应式 locale（用于在模板中判断当前语言）
    const localeReactive = Vue.reactive({ current: i18n.getLocale() });

    app.config.globalProperties.$locale$ = localeReactive;

    // 当语言改变时，更新响应式对象以触发重渲染
    i18n.on('locale-changed', (data) => {
      localeReactive.current = data.locale;
    });
  }
};

/**
 * Mixin：在 setup() 中使用
 * 返回响应式的 t() 函数
 */
window.useI18n = () => {
  const Vue = window.Vue;
  const i18n = window.ZJTi18n;

  // 创建响应式的 locale 对象（用于追踪语言变化）
  const localeRef = Vue.ref(i18n.getLocale());

  // 监听语言变化
  i18n.on('locale-changed', (data) => {
    localeRef.value = data.locale;
  });

  // 返回响应式的 t() 函数
  return {
    t: (key, params) => i18n.t(key, params),
    locale: localeRef,
    getLocale: () => i18n.getLocale(),
    setLocale: (locale, namespaces) => i18n.setLocale(locale, namespaces)
  };
};
