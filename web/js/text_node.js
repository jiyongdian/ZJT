// ============================
// text_node.js - 文本节点
// 使用 createNodeBase 基类工厂
// ============================

(function() {

  var TEXT_NODE_PORTS = [
    { direction: 'output', titleI18nKey: 'text_node_output_port' }
  ];

  function createTextNode(opts) {
    return createNodeBase({
      type: 'text',
      title: function() { return window.t ? window.t('text_node_title') : '文本'; },
      defaultData: { content: '' },
      ports: TEXT_NODE_PORTS,
      cssClass: 'text-node',
      width: 280,
      height: 200,
      titleIcon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;"><path d="M4 6H20M4 12H20M4 18H14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
      bodyHtml: function() {
        var charsLabel = window.t ? window.t('text_node_chars') : '字符';
        return '<div class="field field-always-visible">' +
          '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">' +
            '<div class="label" style="margin: 0;" data-i18n="text_node_content_label">' + (window.t ? window.t('text_node_content_label') : '文本内容') + '</div>' +
            '<button class="mini-btn text-expand-btn" type="button" style="font-size: 11px; padding: 4px 8px;" title="' + (window.t ? window.t('script_expand_btn') : '放大编辑') + '">\u2922</button>' +
          '</div>' +
          '<textarea class="text-content" rows="4" placeholder="' + (window.t ? window.t('text_node_placeholder') : '输入文本内容...') + '" style="resize: vertical; min-height: 80px;"></textarea>' +
          '<div class="text-char-count" style="text-align: right; font-size: 11px; color: var(--muted); margin-top: 4px;">0 ' + charsLabel + '</div>' +
        '</div>';
      },
      onCreated: function(node, el) {
        var contentEl = el.querySelector('.text-content');
        var expandBtn = el.querySelector('.text-expand-btn');
        var charCountEl = el.querySelector('.text-char-count');

        contentEl.addEventListener('input', function() {
          node.data.content = contentEl.value;
          charCountEl.textContent = contentEl.value.length + ' ' + (window.t ? window.t('text_node_chars') : '字符');
        });

        expandBtn.addEventListener('click', function(e) {
          e.stopPropagation();
          showPromptExpandModal(contentEl, '文本内容', function(newValue) {
            node.data.content = newValue;
            contentEl.value = newValue;
            charCountEl.textContent = newValue.length + ' ' + (window.t ? window.t('text_node_chars') : '字符');
          });
        });
      }
    }, opts);
  }

  var createTextNodeWithData = createNodeWithDataFactory(
    createTextNode,
    function(el, node) {
      var contentEl = el.querySelector('.text-content');
      var charCountEl = el.querySelector('.text-char-count');
      if (contentEl && node.data.content) {
        contentEl.value = node.data.content;
      }
      if (charCountEl && node.data.content) {
        charCountEl.textContent = node.data.content.length + ' ' + (window.t ? window.t('text_node_chars') : '字符');
      }
    }
  );

  // 注册到全局
  window.createTextNode = createTextNode;
  window.createTextNodeWithData = createTextNodeWithData;

  // 注册到节点注册表
  registerNodeType('text', {
    createFn: createTextNode,
    createWithDataFn: createTextNodeWithData
  });

})();
