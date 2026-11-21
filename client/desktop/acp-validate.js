/* Checks for everything the app window may ask of the agents (acp-agents.js). The window is a web page: nothing it sends is trusted. The main process
 * checks each value here before it reaches an agent, a file path or a process; the window never receives paths, environment variables or tokens back. */
const KINDS = ["claude", "codex"];
const ID = /^[\w-]{1,64}$/;
const MAX_TEXT = 100 * 1024;
const MAX_IMAGES = 6;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_REFS = 50;
const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];
const CHOICES = ["once", "chat", "deny"];
const REF_KINDS = ["scene", "time", "range", "element", "word", "region", "layer"];

const fail = (message) => { throw new Error(message); };

function kind(v) { return KINDS.includes(v) ? v : fail("Choose Claude Code or Codex."); }
function id(v, what = "id") { return typeof v === "string" && ID.test(v) ? v : fail(`That ${what} is not valid.`); }
function text(v) {
  if (typeof v !== "string" || !v.trim()) fail("Write a message first.");
  if (Buffer.byteLength(v, "utf8") > MAX_TEXT) fail("That message is too long (the limit is 100 kB).");
  return v;
}
function image(v) {
  if (!v || typeof v !== "object" || !IMAGE_TYPES.includes(v.mime) || typeof v.data !== "string") fail("A picture must be a PNG, JPEG or WebP.");
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(v.data)) fail("A picture is not valid.");
  if (Math.floor(v.data.length * 3 / 4) > MAX_IMAGE_BYTES) fail("A picture is larger than 5 MB.");
  return { mime: v.mime, data: v.data };
}
function images(v) {
  if (v == null) return [];
  if (!Array.isArray(v) || v.length > MAX_IMAGES) fail(`At most ${MAX_IMAGES} pictures can be sent.`);
  return v.map(image);
}
function refs(v) {
  if (v == null) return [];
  if (!Array.isArray(v) || v.length > MAX_REFS) fail(`At most ${MAX_REFS} references can be sent.`);
  return v.map((r) => {
    if (!r || typeof r !== "object" || !REF_KINDS.includes(r.kind)) fail("A reference is not valid.");
    const out = { kind: r.kind };
    for (const key of ["scene", "element", "layer", "word"]) if (r[key] != null) out[key] = String(r[key]).slice(0, 64);
    for (const key of ["t", "from", "to", "index"]) if (r[key] != null) { if (!Number.isFinite(r[key])) fail("A reference is not valid."); out[key] = r[key]; }
    if (r.label != null) out.label = String(r.label).slice(0, 200);
    return out;
  });
}
function choice(v) { return CHOICES.includes(v) ? v : fail("Choose Allow once, Allow for this chat or Deny."); }

module.exports = { kind, id, text, image, images, refs, choice, KINDS, CHOICES, MAX_TEXT, MAX_IMAGES, MAX_IMAGE_BYTES, MAX_REFS };
