const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(
  path.join(__dirname, '../../web/marketing_agent.html'),
  'utf8'
);

assert.match(
  html,
  /function getLLMModelSelectionKey\(model\)/,
  'LLM selection should use a composite key helper'
);

assert.match(
  html,
  /:key="getLLMModelSelectionKey\(model\)"/,
  'LLM dropdown rows should be keyed by model and vendor'
);

assert.match(
  html,
  /selectedLLMModelKey === getLLMModelSelectionKey\(model\)/,
  'LLM selected styles should compare model and vendor'
);

assert.match(
  html,
  /marketing_selected_llm_vendor_id/,
  'LLM preference persistence should include vendor_id'
);

assert.match(
  html,
  /vendorName === 'volcengine'[\s\S]*vendorName === 'zjt_api'/,
  'duplicate model names should prefer volcengine before zjt_api'
);

console.log('marketing_agent LLM vendor selection tests passed');
