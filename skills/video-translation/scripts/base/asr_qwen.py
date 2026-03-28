#!/usr/bin/env python3
#
# Qwen3-ASR 语音转录脚本
#
# 用法: python asr_qwen.py <音频文件> -o <输出JSON>
# 输出: 包含词级时间戳和句子分割的JSON文件
#

import argparse
import json
import sys
import os
import logging
import tempfile
from pathlib import Path

import ffmpeg
import torch
import numpy as np
from qwen_asr import Qwen3ASRModel

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_silero_vad(device: str = "cpu"):
    """
    加载 Silero VAD 模型用于语音活动检测。
    """
    logger.info("正在加载 Silero VAD 模型...")
    try:
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False
        )
        model.to(device)
        return model, utils
    except Exception as e:
        logger.error(f"加载 Silero VAD 模型失败: {e}")
        sys.exit(1)

def detect_speech_segments(
    audio_path: str,
    model,
    utils,
    device: str = "cpu",
    sampling_rate: int = 16000,
    threshold: float = 0.2,
    min_speech_duration: float = 0.2,
    min_silence_duration: float = 0.1
) -> list:
    """
    使用 Silero VAD 检测音频中的语音片段。
    """
    logger.info("正在检测语音片段...")

    # Use ffmpeg-python to resample to 16kHz mono (avoids librosa/scipy resample_f_p)
    fd, temp_wav = tempfile.mkstemp(suffix=".16k.wav")
    os.close(fd)
    try:
        (
            ffmpeg
            .input(str(audio_path))
            .output(
                temp_wav,
                ar=sampling_rate,
                ac=1,
                format="wav",
            )
            .run(quiet=True, overwrite_output=True)
        )

        import soundfile as sf
        waveform, sr = sf.read(temp_wav)
        if len(waveform.shape) > 1:
            waveform = waveform.mean(axis=1)
        # Silero VAD and downstream expect float32; avoid dtype issues with resample
        waveform = np.ascontiguousarray(waveform.astype(np.float32))

    except Exception as e:
        logger.error(f"Failed to load/resample audio with ffmpeg: {e}")
        # Fallback: load without resampling then use soxr (avoids librosa resample_f_p ufunc error)
        try:
            import soundfile as sf
            import soxr
            # soundfile can read WAV; for MP3 use librosa with sr=None to skip resample
            ext = Path(audio_path).suffix.lower()
            if ext == ".mp3":
                import librosa
                waveform, sr = librosa.load(audio_path, sr=None, dtype=np.float32)
            else:
                waveform, sr = sf.read(audio_path)
            if len(waveform.shape) > 1:
                waveform = waveform.mean(axis=1)
            waveform = np.ascontiguousarray(waveform.astype(np.float32))
            if sr != sampling_rate:
                waveform = soxr.resample(waveform, sr, sampling_rate)
                sr = sampling_rate
        except Exception as e2:
            logger.error(f"Fallback load also failed: {e2}")
            raise e
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except OSError:
                pass

    # VAD 参数
    (get_speech_timestamps, _, _, _, _) = utils

    # 获取语音时间戳
    speech_timestamps = get_speech_timestamps(
        waveform,
        model,
        sampling_rate=sampling_rate,
        threshold=threshold,
        min_speech_duration_ms=min_speech_duration * 1000,
        min_silence_duration_ms=min_silence_duration * 1000
    )

    # 转换为秒
    segments = []
    for ts in speech_timestamps:
        segments.append({
            "start": ts["start"] / sampling_rate,
            "end": ts["end"] / sampling_rate,
            "audio": waveform[ts["start"]:ts["end"]]
        })

    logger.info(f"检测到 {len(segments)} 个语音片段")
    return segments

def load_audio_segment(audio_segment: dict, sampling_rate: int = 16000):
    """
    准备音频片段用于转录。
    """
    return (audio_segment["audio"], sampling_rate)

def transcribe_audio(
    audio_path: str,
    model_size: str = "1.7B",
    device: str = "auto",
    language: str = None,
    return_time_stamps: bool = True
) -> dict:
    """
    使用 Qwen3-ASR 和 VAD 分割转录音频。
    """
    logger.info(f"正在加载 Qwen3-ASR 模型: Qwen3-ASR-{model_size}...")

    # 确定设备
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"使用设备: {device}")

    # 加载 VAD 模型
    vad_model, vad_utils = load_silero_vad(device)

    # 加载 ASR 模型
    try:
        model = Qwen3ASRModel.from_pretrained(
            f"Qwen/Qwen3-ASR-{model_size}",
            dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            device_map=device,
            forced_aligner="Qwen/Qwen3-ForcedAligner-0.6B",
            forced_aligner_kwargs=dict(
                dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
                device_map=device
            )
        )
    except Exception as e:
        logger.error(f"加载模型失败: {e}")
        sys.exit(1)

    # 检测语音片段
    speech_segments = detect_speech_segments(audio_path, vad_model, vad_utils, device)

    logger.info(f"正在转录 {len(speech_segments)} 个片段...")

    output = {
        "language": "Chinese",
        "language_probability": 1.0,
        "duration": 0,
        "segments": []
    }

    # 获取音频总时长
    try:
        import soundfile as sf
        with sf.SoundFile(audio_path) as f:
            output["duration"] = f.frames / f.samplerate
    except Exception as e:
        logger.warning(f"获取音频时长失败: {e}")
        output["duration"] = 0

    # 转录每个片段
    for i, segment in enumerate(speech_segments):
        logger.info(f"正在转录片段 {i+1}/{len(speech_segments)}...")

        try:
            audio_data = load_audio_segment(segment)
            results = model.transcribe(
                audio=audio_data,
                language=language,
                return_time_stamps=return_time_stamps
            )
        except Exception as e:
            logger.error(f"转录片段 {i} 失败: {e}")
            continue

        if not results or not results[0].text.strip():
            logger.warning(f"片段 {i} 转录结果为空")
            continue

        result = results[0]

        # 根据语言类型选择相应的分句规则
        def is_chinese(text):
            """判断文本是否主要包含中文"""
            chinese_chars = 0
            total_chars = 0
            for char in text:
                if '\u4e00' <= char <= '\u9fff':
                    chinese_chars += 1
                if char.isalnum():
                    total_chars += 1
            return chinese_chars / total_chars > 0.5 if total_chars > 0 else False

        def split_chinese_sentences(text):
            """中文分句规则"""
            sentences = []
            temp = []
            for char in text:
                temp.append(char)
                if char in ['。', '！', '？', '；', '!', '?', ';']:
                    sentences.append(''.join(temp).strip())
                    temp = []
                elif char in ['，', ','] and len(''.join(temp).strip()) > 5:
                    sentences.append(''.join(temp).strip())
                    temp = []
            if temp:
                sentences.append(''.join(temp).strip())
            return sentences

        def split_english_sentences(text):
            """英文分句规则"""
            sentences = []
            temp = []
            i = 0
            while i < len(text):
                char = text[i]
                temp.append(char)

                # 英文句子通常以 . ! ? 结尾，后面可能跟空格、引号或换行
                if char in ['.', '!', '?']:
                    # 检查是否是缩写（如 Mr. Mrs. Dr. 等）
                    is_abbreviation = False
                    # 查找可能的缩写模式
                    if char == '.' and i > 0 and i < len(text) - 1:
                        # 检查前面是否是单个字母
                        if i > 0 and text[i-1].isalpha() and len(temp) <= 3:
                            is_abbreviation = True
                        # 检查常见的缩写
                        temp_str = ''.join(temp).strip().lower()
                        if temp_str in ['mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'jr.', 'sr.', 'vs.', 'etc.', 'e.g.', 'i.e.', 'a.k.a.']:
                            is_abbreviation = True

                    if not is_abbreviation:
                        # 找到句子边界，跳过后面的标点和空格
                        j = i + 1
                        while j < len(text) and (text[j].isspace() or text[j] in ['"', "'", ')', ']']):
                            temp.append(text[j])
                            j += 1
                        sentences.append(''.join(temp).strip())
                        temp = []
                        i = j
                        continue

                i += 1

            if temp:
                sentences.append(''.join(temp).strip())
            return sentences

        def split_other_sentences(text):
            """其他语言通用分句规则"""
            sentences = []
            temp = []
            for char in text:
                temp.append(char)
                if char in ['。', '！', '？', '；', '!', '?', ';', '.']:
                    sentences.append(''.join(temp).strip())
                    temp = []
                elif char in ['，', ','] and len(''.join(temp).strip()) > 5:
                    sentences.append(''.join(temp).strip())
                    temp = []
            if temp:
                sentences.append(''.join(temp).strip())
            return sentences

        # 检测文本语言类型
        text = result.text.strip()
        if is_chinese(text):
            sentences = split_chinese_sentences(text)
        elif all(char.isascii() or char.isspace() for char in text) and any(char.isalpha() and char.islower() for char in text):
            sentences = split_english_sentences(text)
        else:
            sentences = split_other_sentences(text)

        # 过滤掉太短的句子并移除尾部标点
        processed_sentences = []
        punctuation_chars = ['。', '！', '？', '；', '，', ',', '!', '?', ';', '.']
        for s in sentences:
            s = s.strip()
            if len(s) >= 2:
                while s and s[-1] in punctuation_chars:
                    s = s[:-1].strip()
                if len(s) >= 2:
                    processed_sentences.append(s)
        sentences = processed_sentences

        logger.info(f"片段 {i} 识别出 {len(sentences)} 个句子")

        # 根据句子重新分割时间戳
        if return_time_stamps and result.time_stamps and len(sentences) > 1:
            # 计算每个单词在文本中的位置
            word_positions = []
            current_pos = 0
            for word_ts in result.time_stamps:
                word = word_ts.text.strip()
                # 找到单词在文本中的位置
                pos = text.find(word, current_pos)
                if pos != -1:
                    word_positions.append({
                        "word": word,
                        "start": segment["start"] + word_ts.start_time,
                        "end": segment["start"] + word_ts.end_time,
                        "pos": pos,
                        "length": len(word)
                    })
                    current_pos = pos + len(word)

            # 根据句子边界划分单词
            for sent_id, sentence in enumerate(sentences):
                sent_start = text.find(sentence)
                if sent_start == -1:
                    continue
                sent_end = sent_start + len(sentence)

                # 找到属于这个句子的单词
                sent_words = []
                sent_word_start = None
                sent_word_end = None

                for wp in word_positions:
                    if wp["pos"] >= sent_start and wp["pos"] + wp["length"] <= sent_end:
                        sent_words.append({
                            "word": wp["word"],
                            "start": wp["start"],
                            "end": wp["end"],
                            "probability": 1.0
                        })
                        if sent_word_start is None or wp["start"] < sent_word_start:
                            sent_word_start = wp["start"]
                        if sent_word_end is None or wp["end"] > sent_word_end:
                            sent_word_end = wp["end"]

                if sent_words:
                    seg_data = {
                        "id": len(output["segments"]) + 1,
                        "start": sent_word_start,
                        "end": sent_word_end,
                        "text": sentence,
                        "words": sent_words
                    }
                    output["segments"].append(seg_data)
        else:
            # 如果没有识别到多个句子，直接添加整个片段
            seg_data = {
                "id": len(output["segments"]) + 1,
                "start": segment["start"],
                "end": segment["end"],
                "text": text,
                "words": []
            }

            if return_time_stamps and result.time_stamps:
                for word_ts in result.time_stamps:
                    seg_data["words"].append({
                        "word": word_ts.text.strip(),
                        "start": segment["start"] + word_ts.start_time,
                        "end": segment["start"] + word_ts.end_time,
                        "probability": 1.0
                    })

            output["segments"].append(seg_data)

    logger.info(f"成功转录 {len(output['segments'])} 个片段")
    return output

def main():
    parser = argparse.ArgumentParser(description="使用 Qwen3-ASR 和 VAD 分割进行语音转录")
    parser.add_argument("audio_file", help="输入音频文件路径")
    parser.add_argument("-o", "--output", default="transcription.json", help="输出 JSON 文件路径")
    parser.add_argument("--model", default="1.7B", help="Qwen3-ASR 模型大小 (0.6B, 1.7B)")
    parser.add_argument("--device", default="auto", help="设备 (auto, cpu, cuda:0, 等)")
    parser.add_argument("--language", default=None, help="语言 (例如: Chinese, English)")
    parser.add_argument("--vad-threshold", default=0.3, type=float, help="VAD 活动阈值 (0-1)")
    parser.add_argument("--min-speech-duration", default=0.3, type=float, help="最小语音持续时间 (秒)")
    parser.add_argument("--min-silence-duration", default=0.15, type=float, help="最小静音持续时间 (秒)")

    args = parser.parse_args()

    audio_path = Path(args.audio_file).resolve()
    if not audio_path.exists():
        logger.error(f"音频文件未找到: {audio_path}")
        sys.exit(1)

    try:
        data = transcribe_audio(
            str(audio_path),
            model_size=args.model,
            device=args.device,
            language=args.language
        )

        output_path = Path(args.output).resolve()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"转录结果已保存到 {output_path}")

    except Exception as e:
        logger.error(f"转录失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()