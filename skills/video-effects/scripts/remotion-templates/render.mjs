import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const entryPoint = path.join(__dirname, 'index.tsx');
const defaultConfigPath = path.join(
  __dirname,
  '..',
  'temp',
  'config.json'
);
const args = process.argv.slice(2);
const configFlag = args.find((arg) => arg.startsWith('--config='));
const configArgIndex = args.findIndex((arg) => arg === '--config');
const configPath =
  (configFlag ? configFlag.split('=')[1] : null) ??
  (configArgIndex >= 0 ? args[configArgIndex + 1] : null) ??
  args[0] ??
  defaultConfigPath;

const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
const chapters = Array.isArray(config.chapterTitles)
  ? config.chapterTitles
  : [];
const keyPhrases = Array.isArray(config.keyPhrases) ? config.keyPhrases : [];
const termDefinitions = Array.isArray(config.termDefinitions)
  ? config.termDefinitions
  : [];
const quotes = Array.isArray(config.quotes) ? config.quotes : [];
const stats = Array.isArray(config.stats) ? config.stats : [];
const bulletPoints = Array.isArray(config.bulletPoints)
  ? config.bulletPoints
  : [];
const socialBars = Array.isArray(config.socialBars) ? config.socialBars : [];
const lowerThirds = Array.isArray(config.lowerThirds) ? config.lowerThirds : [];

const outDir = path.join(__dirname, '.remotion-bundle');
const useServeUrl = Boolean(process.env.REMOTION_SERVE_URL);
const serveUrl =
  process.env.REMOTION_SERVE_URL ??
  (await bundle({
    entryPoint,
    outDir,
    webpackOverride: (config) => config,
  }));

console.log(`serveUrl: ${serveUrl}`);

const outputBaseDir = path.join(__dirname, '..', 'temp');
const slugify = (value) =>
  String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)+/g, '');

const compositionCache = {};
const chromiumOptions = {
  gl: 'angle',
  headless: true,
};
const getComposition = async (id) => {
  if (!compositionCache[id]) {
    compositionCache[id] = await selectComposition({
      serveUrl,
      id,
      inputProps: {config},
      chromiumOptions,
    });
  }
  return compositionCache[id];
};

const renderEffect = async (id, inputProps, outputLocation) => {
  const baseComposition = await getComposition(id);
  const composition = {
    ...baseComposition,
    props: inputProps,
  };
  fs.mkdirSync(path.dirname(outputLocation), {recursive: true});
  await renderMedia({
    composition,
    serveUrl,
    codec: 'prores',
    proResProfile: '4444',
    pixelFormat: 'yuva444p10le',
    imageFormat: 'png',
    preferLossless: true,
    outputLocation,
    inputProps: {config, ...inputProps},
    timeoutInMilliseconds: 120000,
    logLevel: 'error',
    chromiumOptions,
    concurrency: 1,
    onBrowserLog: (log) => {
      console.log(`[browser] ${log.type}: ${log.text}`);
    },
  });
};

let exitCode = 0;
try {
  if (
    chapters.length === 0 &&
    keyPhrases.length === 0 &&
    termDefinitions.length === 0 &&
    quotes.length === 0 &&
    stats.length === 0 &&
    bulletPoints.length === 0 &&
    socialBars.length === 0 &&
    lowerThirds.length === 0
  ) {
    throw new Error('config 中未找到可渲染的数据');
  }

  for (let i = 0; i < chapters.length; i += 1) {
    const chapter = chapters[i];
    const inputProps = {
      number: chapter.number,
      title: chapter.title,
      subtitle: chapter.subtitle,
      theme: config.theme ?? 'notion',
      durationMs: chapter.durationMs ?? 4000,
    };
    const namePart = slugify(chapter.title) || `chapter-${i + 1}`;
    const outputLocation = path.join(
      outputBaseDir,
      `chapterTitles-${i}.mov`
    );

    await renderEffect('ChapterTitle', inputProps, outputLocation);
    console.log(`✅ 完成 chapterTitles-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < keyPhrases.length; i += 1) {
    const phrase = keyPhrases[i];
    const durationMs =
      phrase.durationMs ??
      (typeof phrase.endMs === 'number' && typeof phrase.startMs === 'number'
        ? Math.max(phrase.endMs - phrase.startMs, 0)
        : 2000);
    const inputProps = {
      text: phrase.text,
      style: phrase.style ?? 'emphasis',
      theme: config.theme ?? 'notion',
      position: phrase.position ?? 'top',
      durationMs,
    };
    const namePart = slugify(phrase.text) || `phrase-${i + 1}`;
    const outputLocation = path.join(outputBaseDir, `keyPhrases-${i}.mov`);

    await renderEffect('fancy-text', inputProps, outputLocation);
    console.log(`✅ 完成 keyPhrases-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < termDefinitions.length; i += 1) {
    const term = termDefinitions[i];
    const durationMs =
      term.durationMs ??
      (typeof term.displayDurationSeconds === 'number'
        ? term.displayDurationSeconds * 1000
        : 6000);
    const inputProps = {
      english: term.english,
      description: term.description,
      theme: config.theme ?? 'notion',
      position: term.position,
      durationMs,
    };
    const namePart = slugify(term.english) || `term-${i + 1}`;
    const outputLocation = path.join(
      outputBaseDir,
      `termDefinitions-${i}.mov`
    );

    await renderEffect('term-card', inputProps, outputLocation);
    console.log(`✅ 完成 termDefinitions-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < quotes.length; i += 1) {
    const quote = quotes[i];
    const inputProps = {
      text: quote.text,
      author: quote.author,
      theme: config.theme ?? 'notion',
      position: quote.position ?? 'bottom',
      durationMs: quote.durationMs ?? 5000,
    };
    const namePart = slugify(quote.text) || `quote-${i + 1}`;
    const outputLocation = path.join(outputBaseDir, `quotes-${i}.mov`);

    await renderEffect('quote-callout', inputProps, outputLocation);
    console.log(`✅ 完成 quotes-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < stats.length; i += 1) {
    const stat = stats[i];
    const inputProps = {
      prefix: stat.prefix,
      number: stat.number ?? 0,
      unit: stat.unit,
      label: stat.label,
      theme: config.theme ?? 'notion',
      position: stat.position ?? 'right',
      durationMs: stat.durationMs ?? 4000,
    };
    const namePart = slugify(stat.label) || `stat-${i + 1}`;
    const outputLocation = path.join(outputBaseDir, `stats-${i}.mov`);

    await renderEffect('animated-stats', inputProps, outputLocation);
    console.log(`✅ 完成 stats-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < bulletPoints.length; i += 1) {
    const bullet = bulletPoints[i];
    const inputProps = {
      title: bullet.title,
      points: bullet.points ?? [],
      theme: config.theme ?? 'notion',
      position: bullet.position ?? 'left',
      durationMs: bullet.durationMs ?? 6000,
    };
    const namePart = slugify(bullet.title) || `bullet-${i + 1}`;
    const outputLocation = path.join(outputBaseDir, `bulletPoints-${i}.mov`);

    await renderEffect('bullet-points', inputProps, outputLocation);
    console.log(`✅ 完成 bulletPoints-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < socialBars.length; i += 1) {
    const social = socialBars[i];
    const inputProps = {
      platform: social.platform ?? 'twitter',
      label: social.label ?? '关注',
      handle: social.handle,
      theme: config.theme ?? 'notion',
      position: social.position ?? 'br',
      durationMs: social.durationMs ?? 5000,
    };
    const namePart = slugify(social.handle) || `social-${i + 1}`;
    const outputLocation = path.join(outputBaseDir, `socialBars-${i}.mov`);

    await renderEffect('social-bar', inputProps, outputLocation);
    console.log(`✅ 完成 socialBars-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < lowerThirds.length; i += 1) {
    const lowerThird = lowerThirds[i];
    const inputProps = {
      name: lowerThird.name,
      role: lowerThird.role,
      company: lowerThird.company,
      theme: config.theme ?? 'notion',
      durationMs: lowerThird.durationMs ?? 5000,
    };
    const namePart = slugify(lowerThird.name) || `lower-${i + 1}`;
    const outputLocation = path.join(outputBaseDir, `lowerThirds-${i}.mov`);

    await renderEffect('lower-third', inputProps, outputLocation);
    console.log(`✅ 完成 lowerThirds-${i} -> ${outputLocation}`);
  }
} catch (error) {
  exitCode = 1;
  console.error(error);
} finally {
  if (!useServeUrl) {
    fs.rmSync(outDir, {recursive: true, force: true});
  }
  process.exit(exitCode);
}
