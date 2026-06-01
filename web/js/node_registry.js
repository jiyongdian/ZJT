// ============================
// node_registry.js - 节点类型注册表
// 用于类型分发和工作流恢复
// ============================

/**
 * 节点类型注册表
 * key: 节点类型字符串，如 'text', 'video', 'image'
 * value: { createFn, createWithDataFn }
 */
var nodeRegistry = {};

/**
 * 注册节点类型
 * @param {string} type - 节点类型标识
 * @param {Object} entry
 * @param {Function} entry.createFn - 创建函数 createXxxNode(opts)
 * @param {Function} entry.createWithDataFn - 带数据恢复函数 createXxxNodeWithData(nodeData)
 */
function registerNodeType(type, entry) {
  nodeRegistry[type] = entry;
}

/**
 * 通过注册表恢复节点（替代 workflow.js 中的 if-else 链）
 * @param {Object} nodeData - 节点数据
 */
function restoreNodeByRegistry(nodeData) {
  var entry = nodeRegistry[nodeData.type];
  if (entry && entry.createWithDataFn) {
    entry.createWithDataFn(nodeData);
    return true;
  }
  return false;
}
