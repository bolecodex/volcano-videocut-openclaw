import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export type TermCardTheme = 'notion' | 'cyberpunk' | 'apple' | 'aurora' | 'tiktok';

export type TermCardProps = {
  english: string;
  description: string;
  theme?: TermCardTheme;
  position?: 'lt' | 'lb' | 'rt' | 'rb';
  durationMs?: number;
};

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const themeStyles: Record<
  TermCardTheme,
  {
    wrapper: React.CSSProperties;
    card: React.CSSProperties;
    title: React.CSSProperties;
    subtitle: React.CSSProperties;
    description: React.CSSProperties;
    accent?: React.CSSProperties;
    borderRadius: number;
    borderAngleSpeed: number;
  }
> = {
  notion: {
    wrapper: {
      padding: 0,
    },
    card: {
      background: 'rgba(255, 253, 247, 0.95)',
      border: '1px solid rgba(55, 53, 47, 0.1)',
      borderRadius: 8,
      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.06)',
      padding: '20px 24px',
    },
    title: {
      color: '#37352F',
      fontFamily: '"Georgia", "Noto Serif SC", serif',
      fontWeight: 700,
      fontSize: 26,
    },
    subtitle: {
      color: '#787774',
      fontFamily: '"SF Mono", "Consolas", monospace',
      fontSize: 13,
      background: 'rgba(135, 131, 120, 0.1)',
      padding: '2px 6px',
      borderRadius: 3,
      display: 'inline-block',
    },
    description: {
      color: '#37352F',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
      fontSize: 15,
      lineHeight: 1.7,
      marginTop: 12,
    },
    accent: {
      position: 'absolute',
      left: 0,
      top: 12,
      bottom: 12,
      width: 4,
      background: 'linear-gradient(180deg, #DFAB01, #E16259)',
      borderRadius: '0 2px 2px 0',
    },
    borderRadius: 8,
    borderAngleSpeed: 0,
  },
  cyberpunk: {
    wrapper: {
      padding: 2,
      borderRadius: 6,
    },
    card: {
      background: 'rgba(13, 13, 13, 0.85)',
      border: '1px solid #00F5FF',
      borderRadius: 4,
      boxShadow: '0 0 20px rgba(0, 245, 255, 0.3), inset 0 0 20px rgba(0, 245, 255, 0.1)',
      padding: 24,
      backdropFilter: 'blur(10px)',
    },
    title: {
      color: '#00F5FF',
      fontFamily: '"Orbitron", "STHeiti", sans-serif',
      fontWeight: 700,
      textShadow: '0 0 10px #00F5FF',
      letterSpacing: '0.05em',
    },
    subtitle: {
      color: '#FF00FF',
      fontFamily: '"Courier New", monospace',
      textTransform: 'uppercase',
      letterSpacing: '0.1em',
      fontSize: 14,
    },
    description: {
      color: '#FFFFFF',
      fontFamily: '"STHeiti", sans-serif',
      opacity: 0.9,
      fontSize: 16,
      lineHeight: 1.6,
    },
    borderRadius: 6,
    borderAngleSpeed: 3,
  },
  apple: {
    wrapper: {
      padding: 0,
    },
    card: {
      background: 'rgba(255, 255, 255, 0.72)',
      border: 'none',
      borderRadius: 18,
      boxShadow: '0 4px 30px rgba(0, 0, 0, 0.1)',
      padding: 24,
      backdropFilter: 'blur(20px)',
    },
    title: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Display", "PingFang SC", sans-serif',
      fontWeight: 700,
      fontSize: 28,
      letterSpacing: '-0.02em',
    },
    subtitle: {
      color: '#86868B',
      fontFamily: '-apple-system, "SF Pro Text", sans-serif',
      fontWeight: 400,
      fontSize: 14,
    },
    description: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Text", "PingFang SC", sans-serif',
      fontWeight: 400,
      fontSize: 15,
      lineHeight: 1.5,
      opacity: 0.8,
    },
    borderRadius: 18,
    borderAngleSpeed: 0,
  },
  aurora: {
    wrapper: {
      padding: 2,
      borderRadius: 18,
    },
    card: {
      background: 'rgba(15, 15, 35, 0.9)',
      border: 'none',
      borderRadius: 16,
      boxShadow: '0 8px 32px rgba(102, 126, 234, 0.3)',
      padding: 24,
      backdropFilter: 'blur(12px)',
    },
    title: {
      background: 'linear-gradient(135deg, #667EEA, #F093FB)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      fontFamily: '"Avenir Next", "PingFang SC", sans-serif',
      fontWeight: 700,
      fontSize: 28,
    },
    subtitle: {
      color: '#B8B8D0',
      fontFamily: '"SF Mono", monospace',
      fontSize: 13,
      opacity: 0.8,
    },
    description: {
      color: '#FFFFFF',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
      fontSize: 15,
      lineHeight: 1.6,
      opacity: 0.9,
    },
    borderRadius: 18,
    borderAngleSpeed: 4,
  },
  tiktok: {
    wrapper: {
      padding: 0,
    },
    card: {
      background: 'rgba(11, 11, 11, 0.92)',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      borderRadius: 14,
      boxShadow: '0 8px 20px rgba(0, 0, 0, 0.45)',
      padding: 24,
    },
    title: {
      color: '#FFFFFF',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
      fontWeight: 700,
      textShadow: '-2px 0 0 #25F4EE, 2px 0 0 #FE2C55',
      fontSize: 28,
    },
    subtitle: {
      color: '#B8B8B8',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
      fontSize: 13,
    },
    description: {
      color: '#FFFFFF',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
      fontSize: 15,
      lineHeight: 1.6,
      opacity: 0.9,
    },
    borderRadius: 14,
    borderAngleSpeed: 0,
  },
};

export const TermCard: React.FC<TermCardProps> = ({
  english,
  description,
  theme = 'notion',
  position = 'rt',
  durationMs = 6000,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const totalFrames = Math.min(durationInFrames, msToFrames(durationMs, fps));
  const enterFrames = msToFrames(600, fps);
  const exitFrames = msToFrames(500, fps);
  const exitStart = totalFrames - exitFrames;

  const isLeft = position === 'lt' || position === 'lb';
  const isBottom = position === 'lb' || position === 'rb';

  let enterTranslateX = [isLeft ? -100 : 100, 0] as [number, number];
  let enterScale = [0.8, 1.0] as [number, number];
  let breatheAmplitude = 3;

  if (theme === 'apple') {
    enterTranslateX = [isLeft ? -50 : 50, 0];
    enterScale = [0.95, 1.0];
    breatheAmplitude = 0;
  } else if (theme === 'notion') {
    enterTranslateX = [isLeft ? -80 : 80, 0];
    enterScale = [0.9, 1.0];
    breatheAmplitude = 2;
  } else if (theme === 'cyberpunk') {
    enterTranslateX = [isLeft ? -120 : 120, 0];
    enterScale = [0.85, 1.0];
    breatheAmplitude = 4;
  }

  const enterProgress = spring({
    frame,
    fps,
    config: {damping: 15, stiffness: 180, mass: 1},
    durationInFrames: enterFrames,
  });

  const translateX = interpolate(enterProgress, [0, 1], enterTranslateX);
  const baseScale = interpolate(enterProgress, [0, 1], enterScale);
  const exitOpacity = interpolate(
    frame,
    [exitStart, totalFrames],
    [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const exitTranslate = interpolate(
    frame,
    [exitStart, totalFrames],
    [0, isLeft ? -50 : 50],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const exitScale = interpolate(
    frame,
    [exitStart, totalFrames],
    [1, 0.95],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const breathePhase = Math.max(frame - enterFrames, 0) / fps;
  const breatheOffset =
    frame > enterFrames && frame < exitStart
      ? Math.sin(breathePhase * Math.PI) * breatheAmplitude
      : 0;

  const styleSet = themeStyles[theme];
  const borderAngle =
    styleSet.borderAngleSpeed > 0
      ? (frame / fps) * (360 / styleSet.borderAngleSpeed)
      : 0;
  const borderGradient =
    theme === 'cyberpunk'
      ? `linear-gradient(${borderAngle}deg, #00F5FF, #FF00FF, #00F5FF)`
      : theme === 'aurora'
      ? `linear-gradient(${borderAngle}deg, #667EEA, #764BA2, #F093FB, #F5576C, #667EEA)`
      : 'transparent';

  const cardWidth = 400;
  const marginX = 40;
  const marginY = 40;
  const {width, height} = useVideoConfig();
  const left = isLeft ? marginX : undefined;
  const right = isLeft ? undefined : marginX;
  const top = isBottom ? undefined : Math.max(marginY, 0);
  const bottom = isBottom ? marginY : undefined;

  return (
    <div style={{width: '100%', height: '100%', position: 'relative'}}>
      <div
        style={{
          position: 'absolute',
          left,
          right,
          top,
          bottom,
          padding: styleSet.wrapper.padding,
          borderRadius: styleSet.borderRadius,
          background: borderGradient,
          opacity: exitOpacity,
          transform: `translateX(${translateX + exitTranslate + breatheOffset}px) scale(${baseScale * exitScale})`,
          ...styleSet.wrapper,
        }}
      >
        <div
          style={{
            position: 'relative',
            width: 400,
            borderRadius: styleSet.card.borderRadius,
            ...styleSet.card,
          }}
        >
          {theme === 'notion' && styleSet.accent ? (
            <div style={styleSet.accent} />
          ) : null}
          <div style={{...styleSet.title, marginBottom: 8}}>{english}</div>
          <div style={styleSet.description}>{description}</div>
        </div>
      </div>
    </div>
  );
};
