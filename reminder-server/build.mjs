import {build} from 'esbuild';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('.',import.meta.url));
const licenses=await Promise.all(['@block65/webcrypto-web-push/LICENSE.md','jose/LICENSE.md','uint8array-extras/license'].map(async path=>
 '/*! '+path+'\n'+await readFile(root+'node_modules/'+path,'utf8')+'\n*/'));
await build({absWorkingDir:root,stdin:{contents:'import worker from "./worker.mjs";export default worker;',resolveDir:root,sourcefile:'deploy-entry.mjs'},bundle:true,format:'esm',platform:'browser',outfile:'worker.bundle.mjs',banner:{js:licenses.join('\n')}});
