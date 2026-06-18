const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.join(__dirname, '../..');
const nodesJs = fs.readFileSync(path.join(repoRoot, 'web/js/nodes.js'), 'utf8');
const eventsJs = fs.readFileSync(path.join(repoRoot, 'web/js/events.js'), 'utf8');
const videoWorkflowHtml = fs.readFileSync(path.join(repoRoot, 'web/video_workflow.html'), 'utf8');
const enI18n = JSON.parse(fs.readFileSync(path.join(repoRoot, 'web/i18n/locales/en/video_workflow.json'), 'utf8'));

function sliceBetween(source, startNeedle, endNeedle, label) {
  const start = source.indexOf(startNeedle);
  assert.notEqual(start, -1, `${label} start should exist`);
  const end = source.indexOf(endNeedle, start);
  assert.notEqual(end, -1, `${label} end should exist`);
  return source.slice(start, end);
}

const scriptGridOptions = sliceBetween(
  nodesJs,
  'function populateScriptGridModelOptions()',
  '// 初始化宫格生图模型',
  'script grid model options'
);

assert.equal(
  scriptGridOptions.includes('value="auto"'),
  false,
  'script node grid model selector should not render smart auto mode'
);
assert.match(
  nodesJs,
  /const DEFAULT_GRID_IMAGE_MODEL = 'gpt_image_2'/,
  'grid model default constant should be gpt_image_2'
);
assert.match(
  scriptGridOptions,
  /populateGridImageModelSelect\(gridModelSelect, node\.data\.gridModel\)/,
  'script node grid model selector should default to gpt_image_2'
);

const shotGroupGridOptions = sliceBetween(
  nodesJs,
  "const gridModelSelect = el.querySelector('.shot-group-grid-model')",
  '// 初始化宫格类型选择',
  'shot group grid model options'
);

assert.equal(
  shotGroupGridOptions.includes('value="auto"'),
  false,
  'shot group grid model selector should not render smart auto mode'
);
assert.match(
  shotGroupGridOptions,
  /node\.data\.gridModel\s*=\s*DEFAULT_GRID_IMAGE_MODEL|populateGridImageModelSelect\(gridModelSelect, node\.data\.gridModel\)/,
  'shot group grid model selector should default to gpt_image_2'
);

assert.equal(enI18n.shot_frame_group, 'Act', 'legacy act label should use Act in English if referenced');
assert.equal(enI18n.shot_group_title, 'Act: {title}', 'shot group node title should use Act in English');
assert.equal(enI18n.script_split_grid_btn, 'Split Acts + Grid Generate', 'script grid action should use Acts in English');

assert.equal(
  videoWorkflowHtml.includes('id="menuAddShotGroup"'),
  false,
  'act nodes should not be available in the add-node menu'
);
assert.equal(
  eventsJs.includes("document.getElementById('menuAddShotGroup')"),
  false,
  'act nodes should not have a direct add-menu click handler'
);
assert.match(
  nodesJs,
  /createShotGroupNode\(\{[\s\S]*shotGroupData:/,
  'script splitting should still create act nodes through createShotGroupNode'
);

console.log('video workflow grid model defaults tests passed');
