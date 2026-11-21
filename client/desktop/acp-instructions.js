/* What the agent is told when a conversation starts (shown to the person under Details, AI conversations). */
function instructions({ title, projectId }) {
  const name = String(title || projectId).replace(/[\r\n`]+/g, " ").replace(/\s{2,}/g, " ").slice(0, 120);
  return [
    `You are working inside Ultimate Video Tool on project "${name}" (id ${projectId}).`,
    "Change the video only through the `video-tool` MCP tools. The person sees every change.",
    "Prefer small, precise changes to what they point at.",
    "When the message has a <video_references> block, [1], [2] ... in the text refer to its lines.",
    "When you mention a scene, a moment or an element in your reply, link it as a Markdown link whose target is vt://scene/s3 (text \"scene 3\"), vt://t/12.5 (text \"0:12.5\") or vt://element/s3/2 (text \"the title\").",
    "Never undo a change the person made by hand unless they ask.",
    "Keep replies short: say what you changed.",
  ].join("\n");
}

/** The person's message followed by what they pointed at, one numbered line each, so "[2]" in the text means the second line. */
function toPrompt(text, refs) {
  if (!refs || !refs.length) return text;
  const line = (r, i) => {
    const where = r.kind === "scene" ? `scene ${r.scene}` : r.kind === "time" ? `time ${r.t}s` : r.kind === "range" ? `time ${r.from}s to ${r.to}s`
      : r.kind === "element" ? `element ${r.index ?? ""} of scene ${r.scene}` : r.kind === "word" ? `word ${r.word}` : r.kind === "layer" ? `layer ${r.layer}` : `a region of scene ${r.scene}`;
    return `[${i + 1}] ${where}${r.label ? ` (${r.label})` : ""}`;
  };
  return `${text}\n\n<video_references>\n${refs.map(line).join("\n")}\n</video_references>`;
}

module.exports = { instructions, toPrompt };
