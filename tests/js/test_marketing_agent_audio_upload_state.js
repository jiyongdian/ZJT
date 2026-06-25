const assert = require('assert');
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(
  path.join(__dirname, '..', '..', 'web', 'marketing_agent.html'),
  'utf8'
);

assert(
  html.includes('mediaItem.serverUrl = data.url;') &&
    html.includes('mediaItem.fileUrl = data.url;'),
  'Agent audio upload success must sync both serverUrl and fileUrl on mediaItems'
);

assert(
  html.includes("mediaItems.value.filter(m => m.type === 'audio')") &&
    html.includes("!m.serverUrl"),
  'Agent send flow must wait for uploaded audio serverUrl before collecting audio_urls'
);

console.log('marketing agent audio upload state checks passed');
