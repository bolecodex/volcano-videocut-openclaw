import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export type BulletPointsTheme = 'notion' | 'cyberpunk' | 'apple' | 'aurora' | 'tiktok';
export type BulletPointsPosition =
  | 'top'
  | 'tl'
  | 'tr'
  | 'bottom'
  | 'bl'
  | 'br'
  | 'left'
  | 'lt'
  | 'lb'
  | 'right'
  | 'rt'
  | 'rb';

export type BulletPointsProps = {
  title?: string;
  points: string[];
  theme?: BulletPointsTheme;
  position?: BulletPointsPosition;
  durationMs?: number;
};

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const themeStyles: Record<
  BulletPointsTheme,
  {
    container: React.CSSProperties;
    title: React.CSSProperties;
    icon: React.CSSProperties;
    text: React.CSSProperties;
  }
> = {
  notion: {
    container: {
      background: 'rgba(255, 253, 247, 0.95)',
      borderRadius: 12,
      boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
    },
    title: {
      color: '#37352F',
      fontFamily: '"Georgia", "Noto Serif SC", serif',
    },
    icon: {
      color: '#E16259',
    },
    text: {
      color: '#37352F',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
  },
  cyberpunk: {
    container: {
      background: 'rgba(13, 13, 13, 0.95)',
      border: '1px solid #00F5FF',
      borderRadius: 4,
    },
    title: {
      color: '#00F5FF',
      fontFamily: '"Orbitron", sans-serif',
      textShadow: '0 0 10px #00F5FF',
    },
    icon: {
      color: '#FF00FF',
    },
    text: {
      color: '#FFF',
      fontFamily: '-apple-system, sans-serif',
    },
  },
  apple: {
    container: {
      background: 'rgba(255, 255, 255, 0.85)',
      borderRadius: 20,
      backdropFilter: 'blur(20px)',
    },
    title: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Display", sans-serif',
      fontWeight: 600,
    },
    icon: {
      color: '#0071E3',
    },
    text: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Text", "PingFang SC", sans-serif',
    },
  },
  aurora: {
    container: {
      background: 'rgba(15, 15, 35, 0.9)',
      borderRadius: 16,
      border: '1px solid rgba(102, 126, 234, 0.3)',
    },
    title: {
      background: 'linear-gradient(135deg, #667EEA, #F093FB)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      fontFamily: '"Avenir Next", sans-serif',
    },
    icon: {
      color: '#F093FB',
    },
    text: {
      color: '#FFF',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
  },
  tiktok: {
    container: {
      background: 'rgba(11, 11, 11, 0.92)',
      borderRadius: 14,
      border: '1px solid rgba(255, 255, 255, 0.08)',
    },
    title: {
      color: '#FFFFFF',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
    },
    icon: {
      color: '#25F4EE',
    },
    text: {
      color: '#FFFFFF',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
  },
};

export const BulletPoints: React.FC<BulletPointsProps> = ({
  title,
  points,
  theme = 'notion',
  position = 'left',
  durationMs = 6000,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const totalFrames = Math.min(durationInFrames, msToFrames(durationMs, fps));
  const enterEnd = msToFrames(300, fps);
  const exitStart = msToFrames(durationMs - 600, fps);
  const exitEnd = exitStart + msToFrames(500, fps);

  const containerOpacity = interpolate(
    frame,
    [0, enterEnd, exitStart, exitEnd],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const containerX = interpolate(
    frame,
    [exitStart, exitEnd],
    [0, -20],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const themeStyle = themeStyles[theme];
  const isTikTok = theme === 'tiktok';
  const stableContainerX = isTikTok ? 0 : Math.round(containerX);
  const marginX = Math.max(64, width * 0.08);
  const marginY = Math.max(64, height * 0.1);
  const normalizedPosition = typeof position === 'string' ? position : 'left';
  const anchor =
    normalizedPosition === 'top'
      ? {x: width / 2, y: marginY, alignX: '-50%', alignY: '0%'}
      : normalizedPosition === 'bottom'
        ? {x: width / 2, y: height - marginY, alignX: '-50%', alignY: '-100%'}
        : normalizedPosition === 'left'
          ? {x: marginX, y: height / 2, alignX: '0%', alignY: '-50%'}
          : normalizedPosition === 'right'
            ? {x: width - marginX, y: height / 2, alignX: '-100%', alignY: '-50%'}
            : normalizedPosition === 'tl' || normalizedPosition === 'lt'
              ? {x: marginX, y: marginY, alignX: '0%', alignY: '0%'}
              : normalizedPosition === 'tr' || normalizedPosition === 'rt'
                ? {x: width - marginX, y: marginY, alignX: '-100%', alignY: '0%'}
                : normalizedPosition === 'bl' || normalizedPosition === 'lb'
                  ? {x: marginX, y: height - marginY, alignX: '0%', alignY: '-100%'}
                  : normalizedPosition === 'br' || normalizedPosition === 'rb'
                    ? {x: width - marginX, y: height - marginY, alignX: '-100%', alignY: '-100%'}
                    : {x: marginX, y: height / 2, alignX: '0%', alignY: '-50%'};

  return (
    <div style={{width: '100%', height: '100%', position: 'relative'}}>
      <div
        style={{
          position: 'absolute',
          left: anchor.x,
          top: anchor.y,
          padding: 32,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          opacity: containerOpacity,
          transform: `translate(${anchor.alignX}, ${anchor.alignY}) translate3d(${stableContainerX}px, 0, 0)`,
          backfaceVisibility: 'hidden',
          WebkitFontSmoothing: 'antialiased',
          ...themeStyle.container,
        }}
      >
        {title ? (
          <div style={{fontSize: 28, fontWeight: 700, ...themeStyle.title}}>
            {title}
          </div>
        ) : null}
        <div style={{display: 'flex', flexDirection: 'column', gap: 16}}>
          {points.map((point, index) => {
            const pointStart = msToFrames(300 + index * 400, fps);
            const pointEnd = pointStart + msToFrames(400, fps);
            const pointOpacity = interpolate(
              frame,
              [pointStart, pointEnd],
              [0, 1],
              {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
            );
            const pointX = interpolate(
              frame,
              [pointStart, pointEnd],
              [-20, 0],
              {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
            );
            const stablePointX = isTikTok ? 0 : Math.round(pointX);

            return (
              <div
                key={`${point}-${index}`}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 16,
                  opacity: pointOpacity,
                  transform: `translate3d(${stablePointX}px, 0, 0)`,
                  backfaceVisibility: 'hidden',
                }}
              >
                <div
                  style={{
                    width: 24,
                    height: 24,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: 2,
                    ...themeStyle.icon,
                  }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" width={20} height={20}>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <div style={{fontSize: 22, lineHeight: 1.4, ...themeStyle.text}}>
                  {point}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
