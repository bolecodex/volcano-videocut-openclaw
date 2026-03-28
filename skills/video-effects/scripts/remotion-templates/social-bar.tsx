import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig, Easing} from 'remotion';

export type SocialBarTheme = 'notion' | 'cyberpunk' | 'apple' | 'aurora' | 'tiktok';
export type SocialPlatform = 'twitter' | 'weibo' | 'youtube';
export type SocialBarPosition =
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

export type SocialBarProps = {
  platform?: SocialPlatform;
  label?: string;
  handle: string;
  theme?: SocialBarTheme;
  position?: SocialBarPosition;
  durationMs?: number;
};

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const icons: Record<SocialPlatform, string> = {
  twitter:
    'M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z',
  weibo:
    'M10.098 20.323c-3.977.391-7.414-1.406-7.672-4.02-.259-2.609 2.759-5.047 6.74-5.441 3.979-.394 7.413 1.404 7.671 4.018.259 2.6-2.759 5.049-6.739 5.443z',
  youtube:
    'M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z',
};

const themeStyles: Record<
  SocialBarTheme,
  {
    container: React.CSSProperties;
    icon: React.CSSProperties;
    label: React.CSSProperties;
    handle: React.CSSProperties;
  }
> = {
  notion: {
    container: {
      background: 'rgba(255, 253, 247, 0.95)',
      boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
    },
    icon: {
      color: '#1DA1F2',
    },
    label: {
      color: '#787774',
      fontFamily: '-apple-system, sans-serif',
    },
    handle: {
      color: '#37352F',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
  },
  cyberpunk: {
    container: {
      background: 'rgba(13, 13, 13, 0.95)',
      border: '1px solid #00F5FF',
    },
    icon: {
      color: '#00F5FF',
      filter: 'drop-shadow(0 0 8px #00F5FF)',
    },
    label: {
      color: '#888',
      fontFamily: '"Courier New", monospace',
    },
    handle: {
      color: '#00F5FF',
      fontFamily: '"Orbitron", sans-serif',
      textShadow: '0 0 10px #00F5FF',
    },
  },
  apple: {
    container: {
      background: 'rgba(255, 255, 255, 0.85)',
      borderRadius: 16,
      backdropFilter: 'blur(20px)',
    },
    icon: {
      color: '#1DA1F2',
    },
    label: {
      color: '#86868B',
      fontFamily: '-apple-system, "SF Pro Text", sans-serif',
    },
    handle: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Display", sans-serif',
    },
  },
  aurora: {
    container: {
      background: 'rgba(15, 15, 35, 0.9)',
      border: '1px solid rgba(102, 126, 234, 0.3)',
    },
    icon: {
      color: '#1DA1F2',
    },
    label: {
      color: '#B8B8D0',
      fontFamily: '-apple-system, sans-serif',
    },
    handle: {
      background: 'linear-gradient(135deg, #667EEA, #F093FB)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      fontFamily: '"Avenir Next", sans-serif',
    },
  },
  tiktok: {
    container: {
      background: 'rgba(11, 11, 11, 0.92)',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      boxShadow: '0 8px 20px rgba(0, 0, 0, 0.45)',
    },
    icon: {
      color: '#FFFFFF',
      filter: 'drop-shadow(0 0 6px rgba(37, 244, 238, 0.6))',
    },
    label: {
      color: '#B8B8B8',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
    handle: {
      color: '#FFFFFF',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
      textShadow: '-2px 0 0 #25F4EE, 2px 0 0 #FE2C55',
    },
  },
};

export const SocialBar: React.FC<SocialBarProps> = ({
  platform = 'twitter',
  label = '关注推特',
  handle,
  theme = 'notion',
  position = 'br',
  durationMs = 5000,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const totalFrames = Math.min(durationInFrames, msToFrames(durationMs, fps));
  const exitStart = totalFrames - msToFrames(500, fps);
  const exitEnd = exitStart + msToFrames(400, fps);

  const containerOpacity = interpolate(
    frame,
    [0, msToFrames(500, fps), exitStart, exitEnd],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const containerY = interpolate(
    frame,
    [0, msToFrames(500, fps), exitStart, exitEnd],
    [20, 0, 0, 20],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const pulseStart = msToFrames(800, fps);
  const pulseEnd = pulseStart + msToFrames(1000, fps);
  const pulseProgress = interpolate(
    frame,
    [pulseStart, pulseEnd],
    [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.sin)}
  );
  const pulseScale = 1 + 0.02 * Math.sin(pulseProgress * Math.PI * 2);

  const themeStyle = themeStyles[theme];
  const path = icons[platform];
  const marginX = Math.max(64, width * 0.08);
  const marginY = Math.max(64, height * 0.1);
  const normalizedPosition = typeof position === 'string' ? position : 'br';
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
                    : {x: width - marginX, y: height - marginY, alignX: '-100%', alignY: '-100%'};

  return (
    <div style={{width: '100%', height: '100%', position: 'relative'}}>
      <div
        style={{
          position: 'absolute',
          left: anchor.x,
          top: anchor.y,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '16px 24px',
          borderRadius: 12,
          opacity: containerOpacity,
          transform: `translate(${anchor.alignX}, ${anchor.alignY}) translateY(${containerY}px)`,
          ...themeStyle.container,
        }}
      >
        <div style={{width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', ...themeStyle.icon}}>
          <svg viewBox="0 0 24 24" fill="currentColor" width={28} height={28}>
            <path d={path} />
          </svg>
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: 2}}>
          <span style={{fontSize: 14, opacity: 0.7, ...themeStyle.label}}>{label}</span>
          <span
            style={{
              fontSize: 22,
              fontWeight: 600,
              transform: `scale(${pulseScale})`,
              ...themeStyle.handle,
            }}
          >
            {handle}
          </span>
        </div>
      </div>
    </div>
  );
};
