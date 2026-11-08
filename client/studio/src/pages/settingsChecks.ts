import type { DoctorRow } from "../types";

const CHECKS: Record<string, [string, string, string]> = {
  "Python 3.11": ["App runtime", "The server can run the video app.", "Run the server installer again to repair the app runtime."],
  FFmpeg: ["Reading and saving videos", "The server can open media and save finished videos.", "Run the server installer again to restore the video tools."],
  "FFmpeg NVENC": ["Faster video saving", "Graphics-card video saving is available.", "Optional: videos can still save using the processor, which takes longer."],
  "Node 20+": ["Video drawing tools", "The server can run the scene renderer.", "Run the server installer again to update the drawing tools."],
  HyperFrames: ["Scene renderer", "The scene renderer is installed.", "Run the server installer again to restore the scene renderer."],
  Fonts: ["Letter styles", "The video's letter styles are installed.", "Run the server installer again to restore the letter styles."],
  Icons: ["Symbols", "The video's symbol library is installed.", "Run the server installer again to restore the symbol library."],
  "Music + SFX": ["Music and sound effects", "The built-in sounds are installed.", "Run the server installer again to restore the built-in sounds."],
  "CUDA (CTranslate2)": ["Faster speech reading", "The graphics card can help read speech.", "Optional: speech can still be read using the processor, which takes longer."],
  "GPU build": ["Graphics-card support", "The installed app matches this computer's graphics hardware.", "Run the server installer again so it chooses the right graphics support."],
  "ASR model": ["Speech reader", "A downloaded speech reader is ready.", "Open Voice & speech and download a speech reader."],
  "Picture dictionary": ["Matching words to pictures", "The built-in picture dictionary is ready.", "Run the server installer again to restore the picture dictionary."],
  "Local AI (scene planner)": ["Local AI", "The local AI is ready, or you have chosen built-in rules.", "Check Language AI on the Server page."],
  "Voices (script to speech)": ["Reading scripts aloud", "A voice is available to read your script.", "Open Voice & speech to set up a voice."],
  "Server management": ["Server controls", "The server's control page is installed.", "Run the server installer again to restore its control page."],
};

export function explainCheck(row: DoctorRow) {
  const info = CHECKS[row.name];
  return info ? { title: info[0], message: info[row.ok ? 1 : 2] } : { title: row.name, message: row.ok ? "Ready to use." : "Needs attention. Open Technical details for the repair instructions." };
}
