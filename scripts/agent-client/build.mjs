import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';

await build({
  entryPoints: [fileURLToPath(new URL('./entry.js', import.meta.url))],
  outfile: fileURLToPath(new URL('../../src/prompt_hub/web_assets/agent_react.js', import.meta.url)),
  bundle: true,
  format: 'iife',
  globalName: 'SodaReact',
  define: {'process.env.NODE_ENV': JSON.stringify('production')},
  legalComments: 'eof',
});
