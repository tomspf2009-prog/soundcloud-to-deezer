// Rend quelques images d'une composition pour vérifier la mise en page sans tout calculer.
// Usage : node scripts/stills.mjs <Composition> <dossier> <frame> [<frame>…]
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';

const [id, outDir, ...frames] = process.argv.slice(2);
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const composition = await selectComposition({serveUrl, id});
for (const frame of frames.map(Number)) {
	const output = path.join(outDir, `${id}-${frame}.png`);
	await renderStill({serveUrl, composition, frame, output, scale: 0.5});
	console.log(output);
}
