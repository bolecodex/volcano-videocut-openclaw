import React, {useLayoutEffect} from 'react';
import {Composition, getInputProps} from 'remotion';
import {AnimatedStats} from './animated-stats';
import {BulletPoints} from './bullet-points';
import {ChapterTitle} from './chapter-title';
import {FancyText} from './fancy-text';
import {LowerThird} from './lower-third';
import {QuoteCallout} from './quote-callout';
import {SocialBar} from './social-bar';
import {TermCard} from './term-card';
const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const defaultFps = 30;
const inputProps = getInputProps() as {config?: {videoInfo?: {width?: number; height?: number}}};
const previewVideoInfo = inputProps?.config?.videoInfo ?? {};
const previewWidth =
  typeof previewVideoInfo.width === 'number' ? previewVideoInfo.width : 1920;
const previewHeight =
  typeof previewVideoInfo.height === 'number' ? previewVideoInfo.height : 1080;

const RenderFrameFix: React.FC = () => {
  useLayoutEffect(() => {
    const original = window.requestAnimationFrame;
    window.requestAnimationFrame = (cb: FrameRequestCallback) =>
      window.setTimeout(() => cb(performance.now()), 0);
    return () => {
      window.requestAnimationFrame = original;
    };
  }, []);
  return null;
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <RenderFrameFix />
      <Composition
        id="ChapterTitle"
        component={ChapterTitle}
        durationInFrames={msToFrames(4000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          number: 'Part 1',
          title: '指数增长的本质',
          subtitle: 'The Nature of Exponential Growth',
          theme: 'notion',
          durationMs: 4000,
        }}
      />
      <Composition
        id="animated-stats"
        component={AnimatedStats}
        durationInFrames={msToFrames(4000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          prefix: '增长率',
          number: 240,
          unit: '%',
          label: '计算能力年增长',
          theme: 'notion',
          position: 'right',
          durationMs: 4000,
        }}
      />
      <Composition
        id="bullet-points"
        component={BulletPoints}
        durationInFrames={msToFrames(6000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          title: '核心观点',
          points: ['AI 发展是平滑的指数曲线', '类似摩尔定律的智能增长', '没有突然的奇点时刻'],
          theme: 'notion',
          position: 'left',
          durationMs: 6000,
        }}
      />
      <Composition
        id="fancy-text"
        component={FancyText}
        durationInFrames={msToFrames(2000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          text: '示例文字',
          style: 'emphasis',
          theme: 'notion',
          position: 'top',
          durationMs: 2000,
          safeMargin: 24,
        }}
      />
      <Composition
        id="lower-third"
        component={LowerThird}
        durationInFrames={msToFrames(5000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          name: 'Dario Amodei',
          role: 'CEO',
          company: 'Anthropic',
          theme: 'notion',
          durationMs: 5000,
        }}
      />
      <Composition
        id="quote-callout"
        component={QuoteCallout}
        durationInFrames={msToFrames(5000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          text: 'AI 的发展是一个非常平滑的指数曲线',
          author: '— Dario Amodei',
          theme: 'notion',
          position: 'bottom',
          durationMs: 5000,
        }}
      />
      <Composition
        id="social-bar"
        component={SocialBar}
        durationInFrames={msToFrames(5000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          platform: 'twitter',
          label: '关注推特',
          handle: '@username',
          theme: 'notion',
          position: 'br',
          durationMs: 5000,
        }}
      />
      <Composition
        id="term-card"
        component={TermCard}
        durationInFrames={msToFrames(6000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          english: 'Artificial Intelligence',
          description:
            '人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。',
          theme: 'notion',
          durationMs: 6000,
        }}
      />
    </>
  );
};
