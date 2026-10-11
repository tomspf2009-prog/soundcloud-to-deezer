import React from 'react';
import {Composition} from 'remotion';
import {PROMO_DURATION, Promo} from './Promo';
import {README_DURATION, ReadmeDemo} from './ReadmeDemo';

export const RemotionRoot: React.FC = () => (
	<>
		<Composition id="Promo" component={Promo} durationInFrames={PROMO_DURATION} fps={30} width={1080} height={1920} />
		<Composition id="ReadmeDemo" component={ReadmeDemo} durationInFrames={README_DURATION} fps={30} width={1280} height={720} />
	</>
);
