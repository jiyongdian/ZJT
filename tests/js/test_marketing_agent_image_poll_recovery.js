const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(
  path.join(__dirname, '../../web/marketing_agent.html'),
  'utf8'
);

assert.equal(
  html.includes('function maybeRecoverImageTaskFromAssistantText'),
  true,
  'marketing agent should recover image polling from assistant text when image_task_submitted SSE is missed'
);

assert.equal(
  html.includes('项目ID'),
  true,
  'project id extraction should support Chinese "项目ID: 744" text'
);

const imageHandlerStart = html.indexOf('function handleImageTaskSubmitted');
assert.notEqual(imageHandlerStart, -1, 'image task submitted handler should exist');
const imageHandler = html.slice(imageHandlerStart, imageHandlerStart + 1200);
assert.equal(
  imageHandler.includes('const pollSessionId = currentSessionId.value'),
  true,
  'image task submitted handler should bind polling to the current session'
);
assert.equal(
  imageHandler.includes('activeGenerationPollKeys.add(pollKey)'),
  true,
  'image task submitted handler should dedupe active image polling'
);

const imagePollStart = html.indexOf('function pollAgentImageStatus');
assert.notEqual(imagePollStart, -1, 'image status polling function should exist');
const imagePollEnd = html.indexOf('function handleVideoTaskSubmitted', imagePollStart);
assert.notEqual(imagePollEnd, -1, 'video task handler should follow image polling function');
const imagePoll = html.slice(imagePollStart, imagePollEnd);
assert.equal(
  imagePoll.includes('pollSessionId = currentSessionId.value'),
  true,
  'image status polling function should receive a fallback pollSessionId'
);
assert.equal(
  imagePoll.includes('appendMessageToBackend(') && imagePoll.includes('pollSessionId'),
  true,
  'image status polling should persist final result to the originating session'
);

const collectStart = html.indexOf('function collectGenerationUrls');
assert.notEqual(collectStart, -1, 'generation URL collector should exist');
const collectEnd = html.indexOf('function extractProjectIdsFromText', collectStart);
assert.notEqual(collectEnd, -1, 'project id extraction should follow generation URL collector');
const collectBody = html.slice(collectStart, collectEnd);
assert.equal(
  collectBody.includes('getGenerationUrlKey'),
  true,
  'generation URL collector should canonicalize URLs before dedupe'
);
assert.equal(
  collectBody.indexOf('addUrl(item.file_url)') < collectBody.indexOf('addUrl(item.result_url)'),
  true,
  'generation URL collector should prefer CDN file_url over local result_url'
);
assert.equal(
  collectBody.includes('urlKeys.has(key)'),
  true,
  'generation URL collector should skip duplicate CDN/local URLs for the same file path'
);

console.log('marketing agent image poll recovery tests passed');
