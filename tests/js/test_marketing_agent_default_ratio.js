const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(
  path.join(__dirname, '../../web/marketing_agent.html'),
  'utf8'
);

assert.match(
  html,
  /const selectedRatio = ref\('9:16'\)/,
  'new marketing users should start from portrait ratio before model config loads'
);

assert.match(
  html,
  /getDefaultRatio\(modelKey\)/,
  'ratio refresh should use the selected model default ratio'
);

assert.match(
  html,
  /function selectRatio\(ratio\)/,
  'manual ratio selection should be tracked separately from model defaults'
);

assert.equal(
  html.includes('@click.stop="selectedRatio = ratio.value"'),
  false,
  'ratio buttons should call selectRatio() so user choices are not overwritten'
);

console.log('marketing_agent default ratio tests passed');
