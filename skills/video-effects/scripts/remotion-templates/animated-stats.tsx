import React from 'react';
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export type AnimatedStatsTheme = 'notion' | 'cyberpunk' | 'apple' | 'aurora' | 'tiktok';
export type AnimatedStatsPosition =
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

export type AnimatedStatsProps = {
  prefix?: string;
  number: number;
  unit?: string;
  label?: string;
  theme?: AnimatedStatsTheme;
  position?: AnimatedStatsPosition;
  durationMs?: number;
};

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const themeStyles: Record<
  AnimatedStatsTheme,
  {
    container: React.CSSProperties;
    prefix: React.CSSProperties;
    number: React.CSSProperties;
    unit: React.CSSProperties;
    label: React.CSSProperties;
  }
> = {
  notion: {
    container: {
      background: 'rgba(255, 253, 247, 0.95)',
      borderRadius: 12,
      boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
    },
    prefix: {
      color: '#787774',
      fontFamily: '-apple-system, sans-serif',
    },
    number: {
      color: '#E16259',
      fontFamily: '"Georgia", serif',
    },
    unit: {
      color: '#E16259',
      fontFamily: '"Georgia", serif',
    },
    label: {
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
    prefix: {
      color: '#888',
      fontFamily: '"Courier New", monospace',
    },
    number: {
      color: '#00F5FF',
      fontFamily: '"Orbitron", sans-serif',
      textShadow: '0 0 20px #00F5FF',
    },
    unit: {
      color: '#FF00FF',
      fontFamily: '"Orbitron", sans-serif',
    },
    label: {
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
    prefix: {
      color: '#86868B',
      fontFamily: '-apple-system, "SF Pro Text", sans-serif',
    },
    number: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Display", sans-serif',
      fontWeight: 600,
    },
    unit: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Display", sans-serif',
    },
    label: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Text", sans-serif',
    },
  },
  aurora: {
    container: {
      background: 'rgba(15, 15, 35, 0.9)',
      borderRadius: 16,
      border: '1px solid rgba(102, 126, 234, 0.3)',
    },
    prefix: {
      color: '#B8B8D0',
      fontFamily: '-apple-system, sans-serif',
    },
    number: {
      background: 'linear-gradient(135deg, #667EEA, #F093FB)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      fontFamily: '"Avenir Next", sans-serif',
    },
    unit: {
      background: 'linear-gradient(135deg, #F093FB, #F5576C)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      fontFamily: '"Avenir Next", sans-serif',
    },
    label: {
      color: '#FFF',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
  },
  tiktok: {
    container: {
      background: 'rgba(11, 11, 11, 0.92)',
      borderRadius: 14,
      border: '1px solid rgba(255, 255, 255, 0.08)',
      boxShadow: '0 8px 20px rgba(0, 0, 0, 0.45)',
    },
    prefix: {
      color: '#B8B8B8',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
    number: {
      color: '#FFFFFF',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
      textShadow: '-2px 0 0 #25F4EE, 2px 0 0 #FE2C55',
    },
    unit: {
      color: '#FE2C55',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
    },
    label: {
      color: '#FFFFFF',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
  },
};

export const AnimatedStats: React.FC<AnimatedStatsProps> = ({
  prefix,
  number,
  unit,
  label,
  theme = 'notion',
  position = 'right',
  durationMs = 4000,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const totalFrames = Math.min(durationInFrames, msToFrames(durationMs, fps));
  const enterEnd = msToFrames(400, fps);
  const exitStart = msToFrames(durationMs - 500, fps);
  const exitEnd = exitStart + msToFrames(400, fps);

  const containerOpacity = interpolate(
    frame,
    [0, enterEnd, exitStart, exitEnd],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const containerScale = interpolate(
    frame,
    [0, enterEnd, exitStart, exitEnd],
    [0.9, 1, 1, 0.95],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const countStart = msToFrames(200, fps);
  const countEnd = countStart + msToFrames(1500, fps);
  const countValue = interpolate(
    frame,
    [countStart, countEnd],
    [0, number],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    }
  );

  const themeStyle = themeStyles[theme];
  const displayNumber = Math.round(countValue);
  const marginX = Math.max(64, width * 0.08);
  const marginY = Math.max(64, height * 0.1);
  const normalizedPosition = typeof position === 'string' ? position : 'right';
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
                    : {x: width - marginX, y: height / 2, alignX: '-100%', alignY: '-50%'};

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: anchor.x,
          top: anchor.y,
          padding: '24px 40px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 8,
          opacity: containerOpacity,
          transform: `translate(${anchor.alignX}, ${anchor.alignY}) scale(${containerScale})`,
          ...themeStyle.container,
        }}
      >
        {prefix ? (
          <div style={{fontSize: 18, opacity: 0.7, ...themeStyle.prefix}}>
            {prefix}
          </div>
        ) : null}
        <div style={{display: 'flex', alignItems: 'baseline', gap: 4}}>
          <span style={{fontSize: 72, fontWeight: 700, ...themeStyle.number}}>
            {displayNumber}
          </span>
          {unit ? (
            <span style={{fontSize: 32, fontWeight: 500, ...themeStyle.unit}}>
              {unit}
            </span>
          ) : null}
        </div>
        {label ? (
          <div style={{fontSize: 20, opacity: 0.8, ...themeStyle.label}}>
            {label}
          </div>
        ) : null}
      </div>
    </div>
  );
};
