/**
 * generate-audio.js
 * Generates TTS audio for a storyboard shot's dialogue.
 * Input (stdin): { storyboard_id }
 * Output (stdout): { storyboard_id, local_path, speaker, voice }
 *
 * Uses character's voice from database. Inner dialogue uses softer tone (slower speed).
 */

import fs from 'fs';
import path from 'path';
import { getStoryboard, setStoryboardAudio, listCharacters, readStdin } from './state.js';
import { textToSpeech } from './jimeng.js';

const { storyboard_id } = JSON.parse(await readStdin());

const shot = getStoryboard(storyboard_id);
if (!shot) throw new Error(`Storyboard ${storyboard_id} not found`);
if (!shot.dialogue) throw new Error('This shot has no dialogue');

// Available voices based on subscription
const AVAILABLE_VOICES = [
  'zh_female_wanqudashu_moon_bigtts',      // 湾区大叔
  'zh_female_daimengchuanmei_moon_bigtts', // 呆萌川妹
  'zh_male_guozhoudege_moon_bigtts',       // 广州德哥
  'zh_male_beijingxiaoye_moon_bigtts',     // 北京小爷
  'zh_male_shaonianzixin_moon_bigtts',     // 少年梓辛
  'zh_female_meilinvyou_moon_bigtts',      // 魅力女友
  'zh_male_shenyeboke_moon_bigtts',        // 深夜播客
  'zh_female_sajiaonvyou_moon_bigtts',     // 柔美女友
  'zh_female_yuanqinvyou_moon_bigtts',     // 撒娇学妹
  'zh_male_haoyuxiaoge_moon_bigtts',       // 浩宇小哥
];

// Find speaker's voice
let voice = 'zh_female_shuangkuaisisi_moon_bigtts'; // default
let speaker = shot.speaker;

if (speaker) {
  const characters = listCharacters(shot.project_id);
  const char = characters.find(c => c.name === speaker);
  if (char?.voice && AVAILABLE_VOICES.includes(char.voice)) {
    voice = char.voice;
  } else if (char?.voice) {
    process.stderr.write(`警告: 声音类型 ${char.voice} 不可用，使用默认声音\n`);
  }
}

// Inner dialogue: slower speed for softer tone
const isInner = shot.dialogue_type === 'inner';
const speedRatio = isInner ? 0.85 : 1.0;

const buf = await textToSpeech(shot.dialogue, { voice, speedRatio });

const audioDir = path.join(process.cwd(), '.yiwa', shot.project_id, 'audio');
if (!fs.existsSync(audioDir)) fs.mkdirSync(audioDir, { recursive: true });
const local_path = path.join(audioDir, `${storyboard_id}.mp3`);
fs.writeFileSync(local_path, buf);

setStoryboardAudio(storyboard_id, local_path, shot.project_id);

console.log(JSON.stringify({ storyboard_id, local_path, speaker, voice }));
