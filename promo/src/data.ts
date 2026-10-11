// Sons et artistes inventés : la promo ne montre aucun vrai artiste.
export type Track = {title: string; artist: string; hues: [number, number]};

export const TRACKS: Track[] = [
	{title: 'exclu — nuit blanche', artist: 'Kaïz', hues: [18, 300]},
	{title: 'freestyle (archive 2021)', artist: 'Nova', hues: [200, 280]},
	{title: 'snippet 35s', artist: 'Yssa', hues: [330, 30]},
	{title: 'inédit — prod. maison', artist: 'MZK', hues: [150, 230]},
	{title: 'live au studio', artist: 'Lowkey Sam', hues: [45, 340]},
	{title: 'remix non officiel', artist: 'Dalia', hues: [260, 190]},
];

export const PLAYLIST_URL = 'https://soundcloud.com/kaiz/sets/mes-exclus';
export const PLAYLIST_NAME = 'mes exclus';
