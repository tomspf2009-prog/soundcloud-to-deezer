// Génère la bande-son originale de la vidéo (aucun échantillon externe, donc aucun droit d'auteur) :
//   public/soundtrack-full.wav : instru + bruitages
//   public/soundtrack-sfx.wav  : bruitages seuls (pour mettre une musique TikTok/Instagram par-dessus)
// Les instants sont calés sur src/Promo.tsx (30 i/s, scènes de 100/125/190/135/110 images, transitions de 15).
import fs from 'node:fs';

const SR = 44100;
const FPS = 30;
const DURATION = 20;
const N = SR * DURATION;
const music = new Float32Array(N);
const sfx = new Float32Array(N);
const sec = (frame) => frame / FPS;

// Bruit pseudo-aléatoire déterministe : le rendu est identique à chaque génération.
let seed = 12345;
const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648) * 2 - 1;

function render(buf, t0, dur, fn, gain = 1) {
	const start = Math.round(t0 * SR);
	const len = Math.round(dur * SR);
	const state = {};
	for (let i = 0; i < len && start + i < N; i++) {
		if (start + i < 0) continue;
		buf[start + i] += fn(i / SR, state) * gain;
	}
}

const onePole = (state, key, x, a) => (state[key] = (state[key] ?? 0) + a * (x - (state[key] ?? 0)));
const highpass = (state, key, x, a) => x - onePole(state, key, x, a);

// ------------------------------------------------------------------ instruments

const kick = (buf, t0, gain = 0.9) =>
	render(buf, t0, 0.45, (t, s) => {
		s.ph = (s.ph ?? 0) + (45 + 110 * Math.exp(-t * 25)) / SR;
		return Math.sin(2 * Math.PI * s.ph) * Math.exp(-t * 7) + rnd() * Math.exp(-t * 300) * 0.25;
	}, gain);

const bass808 = (buf, t0, freq, dur, gain = 0.55) =>
	render(buf, t0, dur, (t, s) => {
		s.ph = (s.ph ?? 0) + freq * (1 + 0.06 * Math.exp(-t * 30)) / SR;
		const env = Math.min(1, t * 200) * Math.exp(-t * 1.6) * Math.min(1, (dur - t) * 20);
		return Math.tanh(1.8 * Math.sin(2 * Math.PI * s.ph)) / Math.tanh(1.8) * env;
	}, gain);

const clap = (buf, t0, gain = 0.45) =>
	render(buf, t0, 0.3, (t, s) => {
		const n = highpass(s, 'hp', onePole(s, 'lp', rnd(), 0.5), 0.15);
		const bursts = [0, 0.011, 0.022].reduce((a, d) => a + (t >= d ? Math.exp(-(t - d) * (d === 0.022 ? 22 : 140)) : 0), 0);
		return n * bursts;
	}, gain);

const hat = (buf, t0, gain = 0.16, decay = 75) =>
	render(buf, t0, 0.12, (t, s) => highpass(s, 'b', highpass(s, 'a', rnd(), 0.5), 0.5) * Math.exp(-t * decay), gain);

const pad = (buf, t0, dur, notes, gain = 0.05) =>
	render(buf, t0, dur, (t, s) => {
		let x = 0;
		notes.forEach((f, n) => {
			[-0.004, 0, 0.005].forEach((det, v) => {
				const k = `p${n}${v}`;
				s[k] = ((s[k] ?? (n * 0.37 + v * 0.21) % 1) + (f * (1 + det)) / SR) % 1;
				x += 2 * s[k] - 1;
			});
		});
		const env = Math.min(1, t / 0.35) * Math.min(1, Math.max(0, (dur - t) / 0.4));
		return onePole(s, 'lp2', onePole(s, 'lp', x, 0.12), 0.12) * env;
	}, gain);

// ------------------------------------------------------------------ bruitages

const whoosh = (buf, t0, dur = 0.5, gain = 0.5) =>
	render(buf, t0, dur, (t, s) => {
		const p = t / dur;
		const a = 0.02 + 0.35 * Math.sin(Math.PI * p);
		return onePole(s, 'b', onePole(s, 'a', rnd(), a), a) * Math.sin(Math.PI * p) ** 2;
	}, gain);

const pop = (buf, t0, pitch = 600, gain = 0.32) =>
	render(buf, t0, 0.16, (t, s) => {
		s.ph = (s.ph ?? 0) + pitch * (1 + Math.exp(-t * 60)) / SR;
		return Math.sin(2 * Math.PI * s.ph) * Math.exp(-t * 38);
	}, gain);

const keyTick = (buf, t0, gain = 0.4) =>
	render(buf, t0, 0.03, (t, s) => highpass(s, 'h', rnd(), 0.3) * Math.exp(-t * 500), gain * (0.7 + 0.3 * Math.abs(rnd())));

const click = (buf, t0, gain = 0.5) =>
	render(buf, t0, 0.06, (t, s) => (rnd() * 0.6 + Math.sin(2 * Math.PI * 2200 * t)) * Math.exp(-t * 260), gain);

const ding = (buf, t0, freq, gain = 0.22) =>
	render(buf, t0, 0.7, (t) => (Math.sin(2 * Math.PI * freq * t) + 0.3 * Math.sin(2 * Math.PI * freq * 2.01 * t)) * Math.exp(-t * 6) * Math.min(1, t * 400), gain);

const impact = (buf, t0, gain = 0.8) =>
	render(buf, t0, 1.2, (t, s) => {
		s.ph = (s.ph ?? 0) + (35 + 40 * Math.exp(-t * 8)) / SR;
		return Math.sin(2 * Math.PI * s.ph) * Math.exp(-t * 3.5) + onePole(s, 'n', rnd(), 0.08) * Math.exp(-t * 12) * 0.6;
	}, gain);

const buzz = (buf, t0, gain = 0.2) =>
	render(buf, t0, 0.5, (t, s) => {
		const f = t < 0.2 ? 330 : 220;
		s.ph = ((s.ph ?? 0) + f / SR) % 1;
		const env = (t < 0.2 ? Math.exp(-t * 6) : Math.exp(-(t - 0.2) * 5)) * Math.min(1, t * 300);
		return onePole(s, 'lp', 2 * s.ph - 1, 0.1) * env;
	}, gain);

const riser = (buf, t0, dur, gain = 0.3) =>
	render(buf, t0, dur, (t, s) => {
		const p = t / dur;
		s.ph = (s.ph ?? 0) + (200 + 1000 * p * p) / SR;
		return (onePole(s, 'n', rnd(), 0.02 + 0.4 * p) * 0.8 + Math.sin(2 * Math.PI * s.ph) * 0.25) * p * p;
	}, gain);

// Même courbe que Easing.bezier(0.65, 0, 0.35, 1) dans la vidéo.
function bezier(x1, y1, x2, y2) {
	const coord = (t, a, b) => 3 * (1 - t) ** 2 * t * a + 3 * (1 - t) * t ** 2 * b + t ** 3;
	return (x) => {
		let lo = 0;
		let hi = 1;
		for (let i = 0; i < 40; i++) {
			const mid = (lo + hi) / 2;
			if (coord(mid, x1, x2) < x) lo = mid;
			else hi = mid;
		}
		return coord((lo + hi) / 2, y1, y2);
	};
}
const easeInOut = bezier(0.65, 0, 0.35, 1);

// ------------------------------------------------------------------ l'instru (150 BPM, rythme trap « half-time »)

const BEAT = sec(12); // 0,4 s
const DROP = sec(42); // pile sur « …dans Deezer ? »
const BAR = 4 * BEAT;
const STEP = BEAT / 4;
const CHORDS = [
	{bass: 55.0, pad: [220.0, 261.63, 329.63]}, // la mineur
	{bass: 43.65, pad: [174.61, 220.0, 261.63]}, // fa
	{bass: 65.41, pad: [261.63, 329.63, 392.0]}, // do
	{bass: 49.0, pad: [196.0, 246.94, 293.66]}, // sol
];

pad(music, 0, DROP + 0.05, CHORDS[0].pad, 0.035);
riser(music, 0.1, DROP - 0.1, 0.22);
for (let bar = 0; DROP + bar * BAR < DURATION; bar++) {
	const t = DROP + bar * BAR;
	const chord = CHORDS[bar % 4];
	pad(music, t, BAR + 0.05, chord.pad);
	for (const step of [0, 6, 10]) {
		kick(music, t + step * STEP, 0.85);
		bass808(music, t + step * STEP, chord.bass, (step === 10 ? 6 : step === 6 ? 4 : 6) * STEP);
	}
	clap(music, t + 8 * STEP);
	for (let step = 0; step < 16; step += 2) hat(music, t + step * STEP, step % 4 ? 0.11 : 0.16);
	if (bar % 2 === 1) for (const step of [13, 14, 15]) hat(music, t + step * STEP, 0.1); // roulement
}

// ------------------------------------------------------------------ bruitages calés sur l'image

const S = [0, 85, 195, 370, 490]; // début de chaque scène (en images)

// 1. Accroche
pop(sfx, sec(S[0] + 1), 520);
pop(sfx, sec(S[0] + 9), 660);
impact(sfx, sec(S[0] + 42), 0.7);
whoosh(sfx, sec(85), 0.55);
// 2. Le problème
for (let i = 0; i < 5; i++) pop(sfx, sec(S[1] + 6 + i * 6), 420 + i * 60, 0.22);
buzz(sfx, sec(S[1] + 62));
whoosh(sfx, sec(S[1] + 70), 0.6, 0.25);
whoosh(sfx, sec(195), 0.5, 0.35);
// 3. La solution : frappe du lien, clic, un « ding » par son copié, carillon final
for (let f = S[2] + 22; f < S[2] + 62; f += 2) keyTick(sfx, sec(f) + rnd() * 0.01);
click(sfx, sec(S[2] + 84));
let copied = 0;
for (let f = S[2] + 92; f <= S[2] + 172; f++) {
	const n = Math.floor(easeInOut((f - (S[2] + 92)) / 80) * 6 + 0.001);
	if (n > copied) {
		ding(sfx, sec(f), [784, 880, 988, 1047, 1175, 1319][n - 1]);
		copied = n;
	}
}
[1047, 1319, 1568].forEach((f, i) => ding(sfx, sec(S[2] + 174) + i * 0.07, f, 0.2));
whoosh(sfx, sec(370), 0.5, 0.45);
// 4. Le résultat : le téléphone monte, chaque son arrive
whoosh(sfx, sec(S[3] + 2), 0.45, 0.3);
for (let i = 0; i < 6; i++) pop(sfx, sec(S[3] + 18 + i * 10), 500 + i * 70, 0.24);
whoosh(sfx, sec(490), 0.5, 0.3);
// 5. Appel à l'action
impact(sfx, sec(S[4] + 1), 0.6);
for (const [i, d] of [22, 28, 34].entries()) pop(sfx, sec(S[4] + d), 600 + i * 120, 0.25);
[1319, 1568, 2093].forEach((f, i) => ding(sfx, sec(S[4] + 45) + i * 0.06, f, 0.18));

// ------------------------------------------------------------------ mixage et export

function master(...tracks) {
	const out = new Float32Array(N);
	for (const [buf, gain] of tracks) for (let i = 0; i < N; i++) out[i] += buf[i] * gain;
	const fadeOut = Math.round(0.6 * SR);
	for (let i = 0; i < fadeOut; i++) out[N - 1 - i] *= i / fadeOut;
	let peak = 0;
	for (let i = 0; i < N; i++) {
		out[i] = Math.tanh(out[i] * 1.2);
		peak = Math.max(peak, Math.abs(out[i]));
	}
	for (let i = 0; i < N; i++) out[i] *= 0.84 / peak; // -1,5 dBFS : marge pour l'encodage AAC
	return out;
}

// Stéréo (gauche = droite) : une piste mono serait baissée de 3 dB au mixage de la vidéo.
function writeWav(path, data) {
	const bytes = data.length * 4;
	const buf = Buffer.alloc(44 + bytes);
	buf.write('RIFF', 0);
	buf.writeUInt32LE(36 + bytes, 4);
	buf.write('WAVEfmt ', 8);
	buf.writeUInt32LE(16, 16);
	buf.writeUInt16LE(1, 20); // PCM
	buf.writeUInt16LE(2, 22); // stéréo
	buf.writeUInt32LE(SR, 24);
	buf.writeUInt32LE(SR * 4, 28);
	buf.writeUInt16LE(4, 32);
	buf.writeUInt16LE(16, 34);
	buf.write('data', 36);
	buf.writeUInt32LE(bytes, 40);
	data.forEach((v, i) => {
		const sample = Math.round(Math.max(-1, Math.min(1, v)) * 32767);
		buf.writeInt16LE(sample, 44 + i * 4);
		buf.writeInt16LE(sample, 46 + i * 4);
	});
	fs.writeFileSync(path, buf);
	console.log(path);
}

writeWav('public/soundtrack-full.wav', master([music, 0.5], [sfx, 1]));
writeWav('public/soundtrack-sfx.wav', master([sfx, 1]));
