import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadMontserrat} from '@remotion/google-fonts/Montserrat';

export const {fontFamily: TITLE} = loadMontserrat('normal', {
	weights: ['700', '800', '900'],
	subsets: ['latin', 'latin-ext'],
});
export const {fontFamily: BODY} = loadInter('normal', {
	weights: ['400', '500', '600', '700'],
	subsets: ['latin', 'latin-ext'],
});

// Les couleurs de l'icône : orange SoundCloud -> violet Deezer.
export const C = {
	bg: '#0D0A14',
	orange: '#FF5500',
	purple: '#A238FF',
	violet: '#7B2FF7',
	white: '#FFFFFF',
	grey: '#A59FB5',
	green: '#1E8E3E',
	neon: '#3BE07E',
	red: '#FF4D5E',
};
export const GRADIENT = `linear-gradient(135deg, ${C.orange}, ${C.purple})`;

export const gradientText: React.CSSProperties = {
	background: GRADIENT,
	WebkitBackgroundClip: 'text',
	backgroundClip: 'text',
	color: 'transparent',
};
