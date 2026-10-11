import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {BODY, C, GRADIENT, TITLE} from './theme';
import {Track, PLAYLIST_NAME, TRACKS} from './data';

// ---------------------------------------------------------------- covers & cartes

export const Cover: React.FC<{hues: [number, number]; size: number; seed: number; radius?: number}> = ({
	hues,
	size,
	seed,
	radius = 12,
}) => (
	<div
		style={{
			width: size,
			height: size,
			borderRadius: radius,
			overflow: 'hidden',
			position: 'relative',
			flexShrink: 0,
			background: `linear-gradient(${(seed * 47) % 360}deg, hsl(${hues[0]} 95% 58%), hsl(${hues[1]} 85% 40%))`,
		}}
	>
		<div
			style={{
				position: 'absolute',
				width: size * 0.9,
				height: size * 0.9,
				borderRadius: '50%',
				left: -size * 0.25 + ((seed * 13) % 20) / 100 * size,
				top: size * 0.4,
				background: 'rgba(255,255,255,0.20)',
			}}
		/>
		<div
			style={{
				position: 'absolute',
				width: size * 0.45,
				height: size * 0.45,
				borderRadius: '50%',
				right: -size * 0.08,
				top: -size * 0.08,
				background: 'rgba(0,0,0,0.22)',
			}}
		/>
	</div>
);

export const TrackCard: React.FC<{track: Track; index: number; width?: number}> = ({track, index, width = 620}) => (
	<div
		style={{
			width,
			display: 'flex',
			alignItems: 'center',
			gap: 26,
			padding: 22,
			borderRadius: 28,
			background: 'rgba(255,255,255,0.07)',
			border: '1.5px solid rgba(255,255,255,0.12)',
			boxShadow: '0 30px 60px rgba(0,0,0,0.35)',
			fontFamily: BODY,
		}}
	>
		<Cover hues={track.hues} size={112} seed={index + 1} radius={18} />
		<div style={{display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0}}>
			<div style={{color: C.white, fontSize: 36, fontWeight: 700, whiteSpace: 'nowrap'}}>{track.title}</div>
			<div style={{display: 'flex', alignItems: 'center', gap: 14}}>
				<span style={{color: C.grey, fontSize: 28}}>{track.artist}</span>
				<span
					style={{
						color: C.white,
						background: C.orange,
						fontSize: 20,
						fontWeight: 700,
						padding: '4px 12px',
						borderRadius: 999,
					}}
				>
					SoundCloud
				</span>
			</div>
		</div>
	</div>
);

// ---------------------------------------------------------------- décor

export const Waveform: React.FC<{bars?: number; width?: number; height?: number; intensity?: number}> = ({
	bars = 42,
	width = 860,
	height = 220,
	intensity = 1,
}) => {
	const frame = useCurrentFrame();
	const gap = 8;
	const barW = (width - gap * (bars - 1)) / bars;
	return (
		<div style={{display: 'flex', alignItems: 'center', gap, width, height}}>
			{new Array(bars).fill(0).map((_, i) => {
				const wave = Math.sin(frame / 5 + i * 0.55) * 0.5 + Math.sin(frame / 9 - i * 0.3) * 0.35 + 0.15;
				const h = Math.max(10, (0.25 + Math.abs(wave)) * height * 0.75 * intensity);
				return (
					<div
						key={i}
						style={{
							width: barW,
							height: h,
							borderRadius: barW,
							background: `linear-gradient(180deg, ${C.orange}, #FF8A3D)`,
							opacity: 0.55 + 0.45 * Math.abs(wave),
						}}
					/>
				);
			})}
		</div>
	);
};

export const Glow: React.FC = () => {
	const frame = useCurrentFrame();
	const x = Math.sin(frame / 90) * 120;
	const y = Math.cos(frame / 110) * 160;
	return (
		<div style={{position: 'absolute', inset: 0, background: C.bg, overflow: 'hidden'}}>
			<div
				style={{
					position: 'absolute',
					width: 1300,
					height: 1300,
					left: -500 + x,
					top: -350 + y,
					borderRadius: '50%',
					background: `radial-gradient(circle, ${C.orange}55, transparent 62%)`,
				}}
			/>
			<div
				style={{
					position: 'absolute',
					width: 1400,
					height: 1400,
					right: -600 - x,
					bottom: -450 - y,
					borderRadius: '50%',
					background: `radial-gradient(circle, ${C.purple}66, transparent 62%)`,
				}}
			/>
		</div>
	);
};

export const Headline: React.FC<{children: React.ReactNode; delay?: number; size?: number; style?: React.CSSProperties}> = ({
	children,
	delay = 0,
	size = 84,
	style,
}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const p = spring({frame: frame - delay, fps, config: {damping: 16, mass: 0.7}});
	return (
		<div
			style={{
				fontFamily: TITLE,
				fontWeight: 900,
				fontSize: size,
				lineHeight: 1.08,
				color: C.white,
				textAlign: 'center',
				letterSpacing: -1.5,
				opacity: p,
				transform: `translateY(${(1 - p) * 60}px)`,
				...style,
			}}
		>
			{children}
		</div>
	);
};

export const Cursor: React.FC<{x: number; y: number; pressed?: boolean; scale?: number}> = ({x, y, pressed, scale = 1}) => (
	<svg
		width={56 * scale}
		height={56 * scale}
		viewBox="0 0 24 24"
		style={{
			position: 'absolute',
			left: x,
			top: y,
			transform: `scale(${pressed ? 0.85 : 1})`,
			transformOrigin: 'top left',
			filter: 'drop-shadow(0 6px 10px rgba(0,0,0,0.45))',
			zIndex: 10,
		}}
	>
		<path d="M4 2 L4 20 L9 15.5 L12.5 22.5 L15.5 21 L12 14 L19 14 Z" fill="white" stroke="#111" strokeWidth="1.3" strokeLinejoin="round" />
	</svg>
);

// ---------------------------------------------------------------- la fenêtre du programme

export type AppState = {
	typed: number; // 0..1 du lien tapé
	pressed: boolean;
	progress: number; // 0..1
	lines: number; // sons copiés affichés dans le journal
	done: boolean;
};

const Field: React.FC<{label: string; value: string; hint?: boolean; caret?: boolean}> = ({label, value, hint, caret}) => (
	<div style={{display: 'flex', alignItems: 'center', gap: 14}}>
		<div style={{width: 64, fontSize: 21, color: '#222'}}>{label}</div>
		<div
			style={{
				flex: 1,
				height: 46,
				background: 'white',
				border: '1px solid #CFCFD6',
				borderBottom: `2px solid ${caret ? C.violet : '#8A8A94'}`,
				borderRadius: 6,
				display: 'flex',
				alignItems: 'center',
				padding: '0 14px',
				fontSize: 20,
				color: hint ? '#8A8A94' : '#111',
				whiteSpace: 'nowrap',
				overflow: 'hidden',
			}}
		>
			{value}
			{caret ? <span style={{width: 2, height: 24, background: '#111', marginLeft: 2}} /> : null}
		</div>
	</div>
);

const Section: React.FC<{title: string; children: React.ReactNode}> = ({title, children}) => (
	<div style={{border: '1px solid #DADAE0', borderRadius: 8, padding: '14px 20px 18px', position: 'relative', marginTop: 14}}>
		<div style={{position: 'absolute', top: -15, left: 14, background: '#F3F3F5', padding: '0 6px', fontSize: 21, fontWeight: 700, color: '#111'}}>
			{title}
		</div>
		{children}
	</div>
);

export const AppWindow: React.FC<{state: AppState; url: string; width?: number}> = ({state, url, width = 900}) => {
	const frame = useCurrentFrame();
	const shown = url.slice(0, Math.round(url.length * state.typed));
	const total = TRACKS.length;
	const current = Math.min(total, Math.floor(state.progress * total) + 1);
	const status = state.done
		? `Terminé ! ${total} sons dans la playlist « ${PLAYLIST_NAME} ».`
		: state.progress > 0
			? `Son ${current} sur ${total} : téléchargement et envoi sur Deezer…`
			: 'Prêt.';
	return (
		<div
			style={{
				width,
				borderRadius: 14,
				overflow: 'hidden',
				background: '#F3F3F5',
				boxShadow: '0 50px 120px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.08)',
				fontFamily: BODY,
			}}
		>
			<div style={{height: 52, background: '#FFFFFF', display: 'flex', alignItems: 'center', padding: '0 18px', gap: 12, borderBottom: '1px solid #E4E4EA'}}>
				<div style={{width: 26, height: 26, borderRadius: 7, background: GRADIENT, color: 'white', fontSize: 18, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>→</div>
				<div style={{fontSize: 19, color: '#222'}}>SoundCloud vers Deezer</div>
				<div style={{flex: 1}} />
				<div style={{display: 'flex', gap: 30, color: '#555', fontSize: 20}}>
					<span>–</span>
					<span>☐</span>
					<span>✕</span>
				</div>
			</div>
			<div style={{padding: '18px 26px 22px'}}>
				<div style={{fontSize: 36, fontWeight: 700, color: '#111'}}>SoundCloud&nbsp;&nbsp;→&nbsp;&nbsp;Deezer</div>
				<div style={{fontSize: 19, color: '#666', marginTop: 4}}>Copie une playlist SoundCloud dans tes MP3 Deezer, avec les covers d'origine.</div>
				<Section title="1. Ton compte Deezer">
					<div style={{fontSize: 21, fontWeight: 700, color: C.green, marginTop: 6}}>✓ Connecté</div>
				</Section>
				<Section title="2. Ta playlist SoundCloud">
					<div style={{display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8}}>
						<Field
							label="Lien :"
							value={shown || 'https://soundcloud.com/artiste/sets/ma-playlist'}
							hint={!shown}
							caret={state.typed > 0 && state.typed < 1 && frame % 16 < 10}
						/>
						<Field label="Nom :" value="facultatif : sinon le même que sur SoundCloud" hint />
					</div>
				</Section>
				<div
					style={{
						marginTop: 16,
						height: 64,
						borderRadius: 4,
						background: state.pressed ? '#5E1DD1' : C.violet,
						transform: `scale(${state.pressed ? 0.98 : 1})`,
						color: 'white',
						fontSize: 25,
						fontWeight: 700,
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
					}}
				>
					{state.progress > 0 && !state.done ? 'Copie en cours…' : 'Copier vers Deezer'}
				</div>
				<Section title="3. Progression">
					<div style={{fontSize: 20, fontWeight: 700, color: '#111', marginTop: 6}}>{status}</div>
					<div style={{height: 14, background: '#E2E2E8', borderRadius: 7, marginTop: 12, overflow: 'hidden'}}>
						<div style={{width: `${state.progress * 100}%`, height: '100%', background: GRADIENT}} />
					</div>
					<div style={{background: '#FAFAFC', borderRadius: 6, marginTop: 12, padding: '10px 14px', height: 168, overflow: 'hidden', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 6}}>
						{TRACKS.slice(0, state.lines).slice(-5).map((t) => (
							<div key={t.title} style={{fontSize: 19, color: C.green}}>
								✓ {t.artist} - {t.title}
							</div>
						))}
					</div>
				</Section>
			</div>
		</div>
	);
};

// ---------------------------------------------------------------- le téléphone

export const Phone: React.FC<{rowStarts: number[]; width?: number; title?: string}> = ({rowStarts, width = 470, title = PLAYLIST_NAME}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const s = width / 470;
	return (
		<div
			style={{
				width,
				height: 960 * s,
				borderRadius: 64 * s,
				background: '#050407',
				padding: 14 * s,
				boxShadow: `0 60px 140px rgba(0,0,0,0.6), 0 0 0 ${3 * s}px #2A2533`,
				fontFamily: BODY,
			}}
		>
			<div style={{width: '100%', height: '100%', borderRadius: 52 * s, background: '#121016', overflow: 'hidden', position: 'relative'}}>
				<div style={{position: 'absolute', top: 14 * s, left: '50%', transform: 'translateX(-50%)', width: 120 * s, height: 34 * s, borderRadius: 20 * s, background: '#000'}} />
				<div style={{padding: `${74 * s}px ${26 * s}px 0`}}>
					<div style={{display: 'flex', gap: 18 * s, alignItems: 'center'}}>
						<div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', width: 132 * s, height: 132 * s, borderRadius: 14 * s, overflow: 'hidden', flexShrink: 0}}>
							{TRACKS.slice(0, 4).map((t, i) => (
								<Cover key={t.title} hues={t.hues} size={66 * s} seed={i + 1} radius={0} />
							))}
						</div>
						<div style={{minWidth: 0}}>
							<div style={{color: C.grey, fontSize: 15 * s, fontWeight: 600, letterSpacing: 1}}>PLAYLIST PRIVÉE</div>
							<div style={{color: C.white, fontSize: 32 * s, fontWeight: 800, fontFamily: TITLE, marginTop: 4 * s}}>{title}</div>
							<div style={{color: C.grey, fontSize: 16 * s, marginTop: 4 * s}}>{TRACKS.length} titres · Mes MP3</div>
						</div>
					</div>
					<div style={{display: 'flex', alignItems: 'center', gap: 14 * s, marginTop: 22 * s}}>
						<div style={{width: 58 * s, height: 58 * s, borderRadius: '50%', background: C.purple, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
							<div style={{width: 0, height: 0, borderTop: `${11 * s}px solid transparent`, borderBottom: `${11 * s}px solid transparent`, borderLeft: `${18 * s}px solid white`, marginLeft: 5 * s}} />
						</div>
						<div style={{color: C.grey, fontSize: 30 * s}}>♡</div>
						<div style={{color: C.grey, fontSize: 26 * s}}>⋯</div>
					</div>
					<div style={{marginTop: 18 * s, display: 'flex', flexDirection: 'column', gap: 16 * s}}>
						{TRACKS.map((t, i) => {
							const p = spring({frame: frame - rowStarts[i], fps, config: {damping: 14, mass: 0.6}});
							const fly = interpolate(p, [0, 1], [-420 * s, 0]);
							return (
								<div key={t.title} style={{display: 'flex', alignItems: 'center', gap: 16 * s, opacity: interpolate(p, [0, 0.3], [0, 1], {extrapolateRight: 'clamp'})}}>
									<div style={{transform: `translateX(${fly}px) rotate(${(1 - p) * -25}deg)`}}>
										<Cover hues={t.hues} size={70 * s} seed={i + 1} radius={10 * s} />
									</div>
									<div style={{minWidth: 0, transform: `translateX(${(1 - p) * 30}px)`}}>
										<div style={{color: C.white, fontSize: 21 * s, fontWeight: 600, whiteSpace: 'nowrap'}}>{t.title}</div>
										<div style={{color: C.grey, fontSize: 17 * s, marginTop: 3 * s}}>{t.artist}</div>
									</div>
								</div>
							);
						})}
					</div>
				</div>
			</div>
		</div>
	);
};

export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);
