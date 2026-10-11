import React from 'react';
import {Composition} from 'remotion';
import {PROMO_DURATION, Promo} from './Promo';
import {README_DURATION, ReadmeDemo} from './ReadmeDemo';

const vertical = {durationInFrames: PROMO_DURATION, fps: 30, width: 1080, height: 1920} as const;

export const RemotionRoot: React.FC = () => (
	<>
		<Composition id="Promo" component={Promo} {...vertical} defaultProps={{soundtrack: 'full' as const}} />
		<Composition id="PromoBruitages" component={Promo} {...vertical} defaultProps={{soundtrack: 'sfx' as const}} />
		<Composition id="ReadmeDemo" component={ReadmeDemo} durationInFrames={README_DURATION} fps={30} width={1280} height={720} />
	</>
);
