const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(
  path.join(__dirname, '../../web/script_writer.html'),
  'utf8'
);

const mainDisconnectHandlerStart = html.indexOf("status_connection_lost");
assert.notEqual(mainDisconnectHandlerStart, -1, 'main SSE status-check failure branch should exist');
const mainDisconnectHandler = html.slice(
  Math.max(0, mainDisconnectHandlerStart - 500),
  mainDisconnectHandlerStart + 800
);
assert.equal(
  mainDisconnectHandler.includes('resetProcessingState()'),
  true,
  'main SSE status-check failure must reset the sending button and processing state'
);
assert.equal(
  mainDisconnectHandler.includes('hideTypingIndicator()'),
  true,
  'main SSE status-check failure must hide the typing indicator'
);

const reconnectFailureStart = html.indexOf("status_reconnect_final");
assert.notEqual(reconnectFailureStart, -1, 'reconnect status-check failure branch should exist');
const reconnectFailureHandler = html.slice(
  Math.max(0, reconnectFailureStart - 500),
  reconnectFailureStart + 800
);
assert.equal(
  reconnectFailureHandler.includes('resetProcessingState()'),
  true,
  'reconnect status-check failure must reset the sending button and processing state'
);
assert.equal(
  reconnectFailureHandler.includes('showError('),
  true,
  'reconnect status-check failure should surface an actionable error'
);

console.log('script_writer SSE disconnect state tests passed');
