function createTextNode(opts){
  const id = state.nextNodeId++;
  const viewportPos = getViewportNodePosition();
  const x = opts && typeof opts.x === 'number' ? opts.x : viewportPos.x;
  const y = Math.max(MIN_NODE_Y, opts && typeof opts.y === 'number' ? opts.y : viewportPos.y);
  const node = {
    id,
    type: 'text',
    title: window.t ? window.t('text_node_title') : '文本',
    x,
    y,
    data: {
      content: ''
    }
  };
  state.nodes.push(node);

  const el = document.createElement('div');
  el.className = 'node text-node';
  el.dataset.nodeId = String(id);
  el.dataset.type = 'text';
  el.style.left = node.x + 'px';
  el.style.top = node.y + 'px';

  el.innerHTML = `
    <div class="port output" title="${window.t ? window.t('text_node_output_port') : '输出文本'}"></div>
    <div class="node-header">
      <div class="node-title" data-i18n="text_node_title"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;"><path d="M4 6H20M4 12H20M4 18H14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>${window.t ? window.t('text_node_title') : '文本'}</div>
      <button class="icon-btn" title="${window.t ? window.t('node_delete_btn') : '删除'}">×</button>
    </div>
    <div class="node-body">
      <div class="field field-always-visible">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
          <div class="label" style="margin: 0;" data-i18n="text_node_content_label">${window.t ? window.t('text_node_content_label') : '文本内容'}</div>
          <button class="mini-btn text-expand-btn" type="button" style="font-size: 11px; padding: 4px 8px;" title="${window.t ? window.t('script_expand_btn') : '放大编辑'}">⤢</button>
        </div>
        <textarea class="text-content" rows="4" placeholder="${window.t ? window.t('text_node_placeholder') : '输入文本内容...'}" style="resize: vertical; min-height: 80px;"></textarea>
        <div class="text-char-count" style="text-align: right; font-size: 11px; color: var(--muted); margin-top: 4px;">0 ${window.t ? window.t('text_node_chars') : '字符'}</div>
      </div>
    </div>
  `;

  const headerEl = el.querySelector('.node-header');
  const deleteBtn = el.querySelector('.icon-btn');
  const outputPort = el.querySelector('.port.output');
  const contentEl = el.querySelector('.text-content');
  const expandBtn = el.querySelector('.text-expand-btn');
  const charCountEl = el.querySelector('.text-char-count');

  deleteBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    removeNode(id);
  });

  el.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    setSelected(id);
    bringNodeToFront(id);
  });

  headerEl.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if(!state.selectedNodeIds.includes(id)){
      setSelected(id);
    }
    bringNodeToFront(id);
    initNodeDrag(id, e.clientX, e.clientY);
  });

  outputPort.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    state.connecting = { fromId: id, startX: e.clientX, startY: e.clientY };
  });

  contentEl.addEventListener('input', () => {
    node.data.content = contentEl.value;
    charCountEl.textContent = `${contentEl.value.length} 字符`;
  });

  expandBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    showPromptExpandModal(contentEl, '文本内容', (newValue) => {
      node.data.content = newValue;
      contentEl.value = newValue;
      charCountEl.textContent = `${newValue.length} 字符`;
    });
  });

  addDebugButtonToNode(el, node);

  canvasEl.appendChild(el);

  // i18n: 翻译节点内 DOM
  if (typeof window.ZJTi18nDOM !== 'undefined') {
    setTimeout(() => window.ZJTi18nDOM.scanDOM(el), 0);
  }

  setSelected(id);
  return id;
}

function createTextNodeWithData(nodeData){
  const savedNextNodeId = state.nextNodeId;
  state.nextNodeId = nodeData.id;

  createTextNode({ x: nodeData.x, y: nodeData.y });

  state.nextNodeId = Math.max(savedNextNodeId, nodeData.id + 1);

  const node = state.nodes.find(n => n.id === nodeData.id);
  if(!node) return;

  node.title = nodeData.title || '文本';
  Object.assign(node.data, nodeData.data);

  const el = canvasEl.querySelector(`.node[data-node-id="${nodeData.id}"]`);
  if(!el) return;

  const contentEl = el.querySelector('.text-content');
  const charCountEl = el.querySelector('.text-char-count');

  if(contentEl && node.data.content){
    contentEl.value = node.data.content;
  }

  if(charCountEl && node.data.content){
    charCountEl.textContent = `${node.data.content.length} 字符`;
  }
}
