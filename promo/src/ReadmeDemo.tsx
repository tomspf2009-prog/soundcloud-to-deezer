import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {AppWindow, Cursor, Glow, Phone, easeInOut} from './components';
import {PLAYLIST_URL, TRACKS} from './data';
import {C, TITLE} from './theme';

// Démo courte pour le haut du README (GIF en boucle) : la fenêtre à gauche, Deezer à droite.
export const README_DURATION = 240;

export const ReadmeDemo: React.FC = () => {
	const frame = useCurrentFrame();
	const typed = interpolate(frame, [12, 42], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const progress = interpolate(frame, [62, 172], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeInOut});
	const lines = Math.floor(progress * TRACKS.length + 0.001);
	// Chaque son apparaît dans Deezer quand la fenêtre le marque comme copié.
	const rowStarts = TRACKS.map((_, i) => {
		for (let f = 62; f <= 172; f++) {
			const p = interpolate(f, [62, 172], [0, 1], {easing: easeInOut});
			if (Math.floor(p * TRACKS.length + 0.001) > i) return f;
		}
		return 172;
	});
	const state = {typed, pressed: frame >= 54 && frame < 62, progress, lines, done: frame >= 174};
	const cx = interpolate(frame, [0, 10, 44, 54, 64, 84], [700, 560, 560, 430, 430, 820], {extrapolateRight: 'clamp', easing: easeInOut});
	const cy = interpolate(frame, [0, 10, 44, 54, 64, 84], [760, 262, 262, 412, 412, 700], {extrapolateRight: 'clamp', easing: easeInOut});
	const arrow = interpolate(Math.sin(frame / 6), [-1, 1], [-8, 8]);
	return (
		<AbsoluteFill>
			<Glow />
			<AbsoluteFill style={{flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 70}}>
				<div style={{position: 'relative', transform: 'scale(0.66)', width: 900 * 0.66, height: 980 * 0.66, transformOrigin: 'top left'}}>
					<AppWindow state={state} url={PLAYLIST_URL} width={900} />
					<Cursor x={cx} y={cy} pressed={state.pressed} />
				</div>
				<div style={{fontFamily: TITLE, fontWeight: 900, fontSize: 90, color: C.purple, transform: `translateX(${arrow}px)`}}>→</div>
				<Phone rowStarts={rowStarts} width={300} />
			</AbsoluteFill>
		</AbsoluteFill>
	);
};
