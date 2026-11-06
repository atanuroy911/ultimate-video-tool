// Bundles the Cartoon 2 engine (src/) into runtime/vt-story.js for the compositions. React comes from the Studio's node_modules,
// so the server needs nothing new installed. Run: node server/renderer/story/build.mjs
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const here = path.dirname(fileURLToPath(import.meta.url));
await build({
  entryPoints: [path.join(here, 'src', 'entry.tsx')],
  outfile: path.join(here, '..', 'runtime', 'vt-story.js'),
  bundle: true, format: 'iife', minify: true, target: 'chrome110', jsx: 'automatic', legalComments: 'eof',
  nodePaths: [path.join(here, '..', '..', '..', 'client', 'studio', 'node_modules')],
  define: { 'process.env.NODE_ENV': '"production"' },
  banner: { js: '/* Cartoon 2 (story engine) runtime: built from server/renderer/story/src by build.mjs. Do not edit by hand. */' },
});
console.log('built runtime/vt-story.js');
