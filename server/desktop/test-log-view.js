// The server log screen: entries, kinds and views from a log shaped like the real one (desktop.log of an installed server, 2026-11-08).
const assert = require('assert');
const { parseLog, select } = require('./log-view.js');

const raw = [
  '[2026-11-08T16:13:01.513Z]  + tqdm==4.70.1',
  '[2026-11-08T16:13:01.516Z]  + transformers==5.20.2',
  '[2026-11-08T16:13:01.539Z]  + video-tool==1.0.0 (from file:///C:/Users/Roy/AppData/Roaming/runtime)',
  '[2026-11-08T16:14:06.349Z] added 115 packages in 49s',
  '[2026-11-08T16:14:13.053Z] Starting processing API on 8790',
  '[2026-11-08T16:14:26.345Z] INFO:     Started server process [32684]',
  'INFO:     Waiting for application startup.',
  '[2026-11-08T16:15:17.334Z] INFO:     192.168.123.101:50217 - "WebSocket /ws" [accepted]',
  '[2026-11-08T16:15:17.339Z] INFO:     connection open',
  '[2026-11-08T17:28:33.909Z] INFO:     127.0.0.1:62541 - "GET /api/system/gpus HTTP/1.1" 200 OK',
  '[2026-11-08T17:28:36.905Z] INFO:     127.0.0.1:62541 - "GET /api/health HTTP/1.1" 200 OK',
  '[2026-11-08T17:29:00.000Z] INFO:     127.0.0.1:62541 - "POST /api/setup/install HTTP/1.1" 500 Internal Server Error',
  '[2026-11-08T17:29:00.100Z] ERROR:    Exception in ASGI application',
  'Traceback (most recent call last):',
  '  File "x.py", line 1, in <module>',
  'ValueError: boom',
  '[2026-11-08T17:30:00.000Z] WARNING:  The card is nearly full',
].join('\n');

const entries = parseLog(raw);
const kinds = entries.map((e) => e.kind);
assert.equal(entries[0].kind, 'install', 'package lines fold into one entry');
assert.equal(entries[0].count, 4);
assert.match(entries[0].text, /Installed 4 parts/);
assert.ok(entries.some((e) => e.kind === 'event' && e.text === 'Started server process [32684]'), 'the INFO: prefix is dropped');
assert.ok(entries.some((e) => e.text === 'Waiting for application startup.'), 'several records under one stamp become separate entries');
assert.equal(kinds.filter((k) => k === 'request').length, 4, 'websocket, connection and status requests are routine');
const crash = entries.find((e) => /Exception in ASGI/.test(e.text));
assert.equal(crash.kind, 'problem');
assert.match(crash.text, /ValueError: boom/, 'a traceback stays with its error');
assert.ok(entries.some((e) => e.kind === 'problem' && /500/.test(e.text)), 'a failed request is a problem, not routine');
assert.ok(entries.some((e) => e.kind === 'warning'));

const important = select(entries, 'important', '', 300);
assert.ok(important.list.every((e) => e.kind !== 'request' && e.kind !== 'install'));
assert.equal(important.hiddenRequests, 4);
assert.equal(important.problems, 2);
const problems = select(entries, 'problems', '', 300);
assert.ok(problems.list.length === 3 && problems.list.every((e) => e.kind === 'problem' || e.kind === 'warning'));
assert.equal(select(entries, 'everything', '', 300).list.length, entries.length);
assert.equal(select(entries, 'everything', 'transformers', 300).list.length, 1, 'search looks inside folded installs');
const few = select(entries, 'everything', '', 3);
assert.equal(few.list.length, 3);
assert.equal(few.older, entries.length - 3, 'only the newest are drawn; the rest wait behind Show older');
assert.deepEqual(parseLog(''), []);
console.log('Server log view: kinds, folding, views, search and paging pass.');
