/* The name this computer gives itself to every server it connects to: random, made once, kept beside the app's other files. A server uses it to tell computers
 * apart (it lists "Claude on <this computer>" under it); it is not a secret and opens nothing. */
const crypto = require('crypto'), fs = require('fs'), path = require('path');
const OK = /^[A-Za-z0-9_-]{4,40}$/;
function deviceId(home) {
  const file = path.join(home, 'device.json');
  const read = () => { try { const id = JSON.parse(fs.readFileSync(file, 'utf8')).id; return OK.test(id) ? id : ''; } catch { return ''; } };
  const had = read();
  if (had) return had;
  fs.mkdirSync(home, { recursive: true });
  try { fs.writeFileSync(file, JSON.stringify({ id: crypto.randomBytes(4).toString('hex') }), { flag: 'wx' }); } catch (e) { if (e.code !== 'EEXIST') throw e; }
  return read() || crypto.randomBytes(4).toString('hex');       // the app and the helper may both start at once: whoever wrote first is the name
}
module.exports = { deviceId };
