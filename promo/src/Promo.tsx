import React from 'react';
import {AbsoluteFill, Html5Audio, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {slide} from '@remotion/transitions/slide';
import {AppWindow, Cursor, Glow, Headline, Phone, TrackCard, Waveform, easeInOut} from './components';
import {PLAYLIST_URL, TRACKS} from './data';
import {BODY, C, GRADIENT, TITLE, gradientText} from './theme';

// Vidéo verticale 1080x1920 pour TikTok / Reels / Shorts.
// Zone sûre : rien d'important dans les ~240 px du haut ni les ~380 px du bas (boutons des applis).

const T = 15; // durée des transitions
export const SCENES = [100, 125, 190, 135, 110];
export const PROMO_DURATION = SCENES.reduce((a, b) => a + b, 0) - T * (SCENES.length - 1);

const Center: React.FC<{children: React.ReactNode; gap?: number; top?: number}> = ({children, gap = 40, top = 0}) => (
	<AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap, paddingTop: top}}>{children}</AbsoluteFill>
);

const Hook: React.FC = () => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const pop = spring({frame: frame - 42, fps, config: {damping: 11, mass: 0.8}});
	return (
		<Center gap={70}>
			<div>
				<Headline size={118}>Tes exclus</Headline>
				<Headline size={118} delay={8} style={{color: C.orange}}>
					SoundCloud…
				</Headline>
			</div>
			<Waveform intensity={interpolate(frame, [0, 20], [0.2, 1], {extrapolateRight: 'clamp'})} />
			<div
				style={{
					fontFamily: TITLE,
					fontWeight: 900,
					fontSize: 104,
					letterSpacing: -2,
					whiteSpace: 'nowrap',
					opacity: pop,
					transform: `scale(${0.6 + 0.4 * pop})`,
					...gradientText,
					backgroundImage: `linear-gradient(135deg, ${C.purple}, #D08BFF)`,
				}}
			>
				…dans Deezer ?
			</div>
		</Center>
	);
};

const Problem: React.FC = () => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const verdict = spring({frame: frame - 62, fps, config: {damping: 13}});
	const fadeCards = interpolate(frame, [58, 80], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<Center gap={30} top={40}>
			<Headline size={76}>Exclus, snippets, archives…</Headline>
			<div style={{display: 'flex', flexDirection: 'column', gap: 26, marginTop: 30}}>
				{TRACKS.slice(0, 5).map((t, i) => {
					const p = spring({frame: frame - 6 - i * 6, fps, config: {damping: 14}});
					const bob = Math.sin((frame + i * 20) / 18) * 8;
					return (
						<div
							key={t.title}
							style={{
								transform: `translateX(${(i % 2 ? 1 : -1) * (1 - p) * 700 + (i % 2 ? 40 : -40)}px) translateY(${bob}px)`,
								filter: `grayscale(${fadeCards})`,
								opacity: 1 - fadeCards * 0.55,
							}}
						>
							<TrackCard track={t} index={i} />
						</div>
					);
				})}
			</div>
			<div style={{position: 'relative', marginTop: 40, opacity: verdict, transform: `scale(${0.8 + 0.2 * verdict})`}}>
				<div style={{fontFamily: TITLE, fontWeight: 900, fontSize: 76, color: C.white, letterSpacing: -1.5, whiteSpace: 'nowrap', textAlign: 'center'}}>
					Introuvables sur Deezer.
				</div>
				<div
					style={{
						position: 'absolute',
						left: 0,
						bottom: -14,
						height: 12,
						borderRadius: 6,
						background: C.red,
						width: `${interpolate(frame, [70, 90], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}%`,
					}}
				/>
			</div>
		</Center>
	);
};

const Solution: React.FC = () => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const enter = spring({frame, fps, config: {damping: 15}});
	const typed = interpolate(frame, [22, 62], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const progress = interpolate(frame, [92, 172], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeInOut});
	const pressed = frame >= 84 && frame < 92;
	const state = {
		typed,
		pressed,
		progress,
		lines: Math.floor(progress * TRACKS.length + 0.001),
		done: frame >= 174,
	};
	// Curseur, en coordonnées de la fenêtre : champ « Lien », puis bouton, puis il s'écarte.
	const cx = interpolate(frame, [0, 18, 64, 82, 96, 120], [980, 600, 600, 470, 470, 880], {extrapolateRight: 'clamp', easing: easeInOut});
	const cy = interpolate(frame, [0, 18, 64, 82, 96, 120], [1100, 262, 262, 412, 412, 760], {extrapolateRight: 'clamp', easing: easeInOut});
	return (
		<Center gap={50}>
			<Headline size={96}>
				1 lien. <span style={gradientText}>1 clic.</span>
			</Headline>
			<div style={{position: 'relative', opacity: enter, transform: `translateY(${(1 - enter) * 120}px) scale(${0.92 + 0.08 * enter})`}}>
				<AppWindow state={state} url={PLAYLIST_URL} width={960} />
				<Cursor x={cx} y={cy} pressed={pressed} />
			</div>
		</Center>
	);
};

const Result: React.FC = () => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const rise = spring({frame, fps, config: {damping: 16}});
	return (
		<Center gap={44}>
			<div>
				<Headline size={80}>Direct dans ton Deezer</Headline>
				<Headline size={64} delay={34} style={gradientText}>
					avec les covers d'origine
				</Headline>
			</div>
			<div style={{transform: `translateY(${(1 - rise) * 500}px)`}}>
				<Phone rowStarts={TRACKS.map((_, i) => 18 + i * 10)} width={500} />
			</div>
		</Center>
	);
};

const Pill: React.FC<{children: React.ReactNode; delay: number}> = ({children, delay}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const p = spring({frame: frame - delay, fps, config: {damping: 12}});
	return (
		<div
			style={{
				fontFamily: BODY,
				fontWeight: 700,
				fontSize: 40,
				color: C.white,
				padding: '16px 34px',
				borderRadius: 999,
				border: '2px solid rgba(255,255,255,0.25)',
				background: 'rgba(255,255,255,0.08)',
				opacity: p,
				transform: `translateY(${(1 - p) * 40}px)`,
			}}
		>
			{children}
		</div>
	);
};

const Cta: React.FC = () => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const icon = spring({frame, fps, config: {damping: 10, mass: 0.8}});
	const pulse = 1 + Math.sin(frame / 5) * 0.04 * interpolate(frame, [45, 55], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const cta = spring({frame: frame - 45, fps, config: {damping: 12}});
	return (
		<Center gap={44}>
			<Img src={staticFile('icon.png')} style={{width: 260, height: 260, transform: `scale(${icon}) rotate(${(1 - icon) * -30}deg)`}} />
			<div>
				<Headline size={104} delay={8}>
					SoundCloud
				</Headline>
				<Headline size={104} delay={14} style={gradientText}>
					vers Deezer
				</Headline>
			</div>
			<div style={{display: 'flex', gap: 22}}>
				<Pill delay={22}>Gratuit</Pill>
				<Pill delay={28}>Open source</Pill>
				<Pill delay={34}>Windows</Pill>
			</div>
			<div
				style={{
					marginTop: 30,
					fontFamily: TITLE,
					fontWeight: 900,
					fontSize: 70,
					color: C.white,
					padding: '26px 64px',
					borderRadius: 999,
					background: GRADIENT,
					boxShadow: `0 20px 60px ${C.purple}88`,
					opacity: cta,
					transform: `scale(${(0.7 + 0.3 * cta) * pulse})`,
				}}
			>
				Lien en bio ↓
			</div>
			<div style={{fontFamily: BODY, fontSize: 30, color: C.grey, opacity: interpolate(frame, [58, 70], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
				github.com/tomspf2009-prog/soundcloud-to-deezer
			</div>
		</Center>
	);
};

// Bande-son originale générée par scripts/sound.mjs : « full » = instru + bruitages, « sfx » = bruitages seuls.
export type PromoProps = {soundtrack: 'full' | 'sfx'};

export const Promo: React.FC<PromoProps> = ({soundtrack}) => (
	<AbsoluteFill>
		<Html5Audio src={staticFile(`soundtrack-${soundtrack}.wav`)} />
		<Glow />
		<TransitionSeries>
			<TransitionSeries.Sequence durationInFrames={SCENES[0]}>
				<Hook />
			</TransitionSeries.Sequence>
			<TransitionSeries.Transition presentation={slide({direction: 'from-bottom'})} timing={linearTiming({durationInFrames: T})} />
			<TransitionSeries.Sequence durationInFrames={SCENES[1]}>
				<Problem />
			</TransitionSeries.Sequence>
			<TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: T})} />
			<TransitionSeries.Sequence durationInFrames={SCENES[2]}>
				<Solution />
			</TransitionSeries.Sequence>
			<TransitionSeries.Transition presentation={slide({direction: 'from-right'})} timing={linearTiming({durationInFrames: T})} />
			<TransitionSeries.Sequence durationInFrames={SCENES[3]}>
				<Result />
			</TransitionSeries.Sequence>
			<TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: T})} />
			<TransitionSeries.Sequence durationInFrames={SCENES[4]}>
				<Cta />
			</TransitionSeries.Sequence>
		</TransitionSeries>
	</AbsoluteFill>
);
