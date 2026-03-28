#!/usr/bin/env python3
"""
基于 index-TTS2 的标准语复刻，计算片段语速（秒/字）。

输入：
- mapping.json（通常为 output/<xxx>/segments/mapping.json）
- segments 目录（含 segment_*.wav）
- target_language（例如 zh / en）

输出：
- <output_dir>/cloned/segment_XXXX.wav
- <output_dir>/speed_mapping.json
- <output_dir>/speed_summary.json
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import re
import statistics
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

import soundfile as sf
import yaml

INDEX_TTS_REPO = "https://github.com/index-tts/index-tts.git"
SCRIPT_DIR = Path(__file__).resolve().parent
TRANSLATE_VIDEO_ROOT = SCRIPT_DIR.parent.parent
VENDORS_DIR = TRANSLATE_VIDEO_ROOT / "scripts" / "vendors"

STANDARD_TEXT_BY_LANG: dict[str, str] = {
    "zh": "你好",
    "zh-cn": "你好",
    "zh-hans": "你好",
    "zh-tw": "你好",
    "zh-hant": "你好",
    "en": "hello world",
    "en-us": "hello world",
    "en-gb": "hello world",
    "ja": "こんにちは",
    "ko": "안녕하세요",
    "fr": "bonjour",
    "de": "hallo",
    "es": "hola",
    "ru": "привет",
}


def _normalize_lang(lang: str) -> str:
    return lang.strip().lower().replace("_", "-")


def resolve_standard_text(target_language: str, standard_text: str | None) -> str:
    if standard_text and standard_text.strip():
        return standard_text.strip()
    return STANDARD_TEXT_BY_LANG.get(_normalize_lang(target_language), "hello world")


def _contains_cjk(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if (
            0x4E00 <= code <= 0x9FFF  # CJK Unified Ideographs
            or 0x3400 <= code <= 0x4DBF  # CJK Extension A
            or 0x3040 <= code <= 0x30FF  # Hiragana + Katakana
            or 0xAC00 <= code <= 0xD7AF  # Hangul
        ):
            return True
    return False


def count_chars(text: str) -> int:
    """
    统一计数口径：
    - 中日韩文本：按“字/字符”计数（去空白、去标点）
    - 英文等空格分词语言：按“词”计数（hello world -> 2）
    """
    cleaned_chars: list[str] = []
    for ch in text:
        if ch.isspace():
            continue
        if unicodedata.category(ch).startswith("P"):
            continue
        cleaned_chars.append(ch)

    cleaned_text = "".join(cleaned_chars)
    if not cleaned_text:
        return 0

    if _contains_cjk(cleaned_text):
        return len(cleaned_text)

    # 非 CJK：按词计数，保留字母数字及常见撇号连接
    tokens = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", cleaned_text)
    if tokens:
        return len(tokens)

    # 回退：无法分词时仍按字符计数，避免返回 0
    return len(cleaned_text)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = max(0, min(len(sorted_values) - 1, math.ceil(p * len(sorted_values)) - 1))
    return sorted_values[idx]


def segment_duration_from_mapping(seg: dict[str, Any]) -> float:
    """优先使用 mapping.duration，其次回退 end-start。"""
    if "duration" in seg:
        try:
            d = float(seg["duration"])
            return max(0.0, d)
        except Exception:
            pass
    try:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        return max(0.0, end - start)
    except Exception:
        return 0.0


def validate_model_assets(model_dir: Path, cfg_path: Path) -> None:
    """
    在构建 IndexTTS2 前校验本地模型资源是否完整，避免把本地路径误判成 HuggingFace repo id。
    """
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    missing: list[str] = []
    required_files = [
        cfg.get("gpt_checkpoint"),
        cfg.get("w2v_stat"),
        cfg.get("s2mel_checkpoint"),
        cfg.get("emo_matrix"),
        cfg.get("spk_matrix"),
    ]
    for rel in required_files:
        if not rel:
            continue
        p = (model_dir / str(rel).strip()).resolve()
        if not p.exists():
            missing.append(str(p))

    qwen_emo_path = str(cfg.get("qwen_emo_path", "")).strip()
    if qwen_emo_path:
        qwen_dir = (model_dir / qwen_emo_path).resolve()
        if not qwen_dir.exists():
            missing.append(str(qwen_dir))
        else:
            # Qwen tokenizer/model 最小检查
            candidate_tokenizer_files = [
                qwen_dir / "tokenizer.json",
                qwen_dir / "tokenizer_config.json",
            ]
            if not any(p.exists() for p in candidate_tokenizer_files):
                missing.append(
                    f"{qwen_dir} (missing tokenizer files: tokenizer.json/tokenizer_config.json)"
                )

    if missing:
        missing_text = "\n  - ".join(missing)
        raise FileNotFoundError(
            "IndexTTS2 checkpoints are incomplete. Missing required assets:\n"
            f"  - {missing_text}\n\n"
            "Please download model files into the checkpoints directory, for example:\n"
            f"  cd {model_dir.parent}\n"
            "  uv tool install \"huggingface-hub[cli,hf_xet]\"\n"
            "  hf download IndexTeam/IndexTTS-2 --local-dir=checkpoints\n"
        )


def ensure_index_tts_repo(index_tts_dir: Path, clone_if_missing: bool, git_lfs_pull: bool) -> None:
    if index_tts_dir.exists():
        return
    if not clone_if_missing:
        raise FileNotFoundError(
            f"index-tts repo not found: {index_tts_dir}. "
            "Use --clone-index-tts or clone it to scripts/vendors/index-tts."
        )
    index_tts_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", INDEX_TTS_REPO, str(index_tts_dir)], check=True)
    if git_lfs_pull:
        subprocess.run(["git", "lfs", "install"], check=True, cwd=str(index_tts_dir))
        subprocess.run(["git", "lfs", "pull"], check=True, cwd=str(index_tts_dir))


def build_tts(
    index_tts_dir: Path,
    model_dir: Path,
    cfg_path: Path,
    use_fp16: bool,
    use_cuda_kernel: bool,
    use_deepspeed: bool,
    auto_install_missing_deps: bool = False,
):
    # 动态注入 index-tts 仓库，避免强依赖安装在本项目中。
    expected_index_tts_py = (index_tts_dir / ".venv" / "bin" / "python").resolve()
    current_py = Path(sys.executable).resolve()
    if current_py != expected_index_tts_py:
        raise RuntimeError(
            "IndexTTS must run in isolated index-tts environment to avoid dependency conflicts. "
            f"Current: {current_py}, Expected: {expected_index_tts_py}. "
            "Please run via index-tts python or let pipeline/audio_clone auto-switch runtime."
        )

    sys.path.insert(0, str(index_tts_dir))
    install_attempts = 0
    max_install_attempts = 8
    while True:
        try:
            from indextts.infer_v2 import IndexTTS2  # type: ignore
            break
        except ModuleNotFoundError as exc:
            missing_pkg = getattr(exc, "name", None)
            if not auto_install_missing_deps or not missing_pkg or install_attempts >= max_install_attempts:
                raise RuntimeError(
                    "Failed to import IndexTTS2. Missing dependency: "
                    f"{missing_pkg or 'unknown'}. "
                    "You can run: "
                    f"`cd {index_tts_dir} && uv sync --all-extras` "
                    "or re-run with --auto-install-missing-deps."
                ) from exc
            print(f"[speed_profile] auto installing missing dependency: {missing_pkg}")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", missing_pkg],
                check=True,
            )
            install_attempts += 1
        except ImportError as exc:
            msg = str(exc)
            needs_transformers_pin = (
                "QuantizedCacheConfig" in msg
                and "transformers.cache_utils" in msg
            )
            # 对 IndexTTS2 的已知兼容性问题（QuantizedCacheConfig 缺失）做自动修复，
            # 避免用户必须额外传 --auto-install-missing-deps。
            if not needs_transformers_pin or install_attempts >= max_install_attempts:
                raise RuntimeError(
                    "Failed to import IndexTTS2. Ensure index-tts dependencies are installed "
                    f"in its environment. Details: {exc}"
                ) from exc
            print(
                "[speed_profile] auto fixing transformers compatibility "
                "(transformers==4.52.1, tokenizers==0.21.0, json5==0.10.0)"
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "transformers==4.52.1",
                    "tokenizers==0.21.0",
                    "json5==0.10.0",
                ],
                check=True,
            )
            install_attempts += 1
        except Exception as exc:
            raise RuntimeError(
                "Failed to import IndexTTS2. Ensure index-tts dependencies are installed "
                f"in its environment. Details: {exc}"
            ) from exc

    return IndexTTS2(
        cfg_path=str(cfg_path),
        model_dir=str(model_dir),
        use_fp16=use_fp16,
        use_cuda_kernel=use_cuda_kernel,
        use_deepspeed=use_deepspeed,
    )


def run(
    mapping_path: Path,
    segments_dir: Path,
    output_dir: Path,
    target_language: str,
    *,
    standard_text: str | None = None,
    index_tts_dir: Path | None = None,
    model_dir: Path | None = None,
    cfg_path: Path | None = None,
    clone_index_tts: bool = False,
    git_lfs_pull: bool = False,
    use_fp16: bool = False,
    use_cuda_kernel: bool = False,
    use_deepspeed: bool = False,
    auto_install_missing_deps: bool = False,
    skip_existing: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    if not isinstance(mapping, list):
        raise ValueError(f"Invalid mapping format (expect list): {mapping_path}")

    index_tts_dir = (index_tts_dir or (VENDORS_DIR / "index-tts")).resolve()
    ensure_index_tts_repo(index_tts_dir, clone_index_tts, git_lfs_pull)

    model_dir = (model_dir or (index_tts_dir / "checkpoints")).resolve()
    cfg_path = (cfg_path or (model_dir / "config.yaml")).resolve()
    if not cfg_path.exists():
        raise FileNotFoundError(f"config not found: {cfg_path}")
    if not model_dir.exists():
        raise FileNotFoundError(f"model dir not found: {model_dir}")
    validate_model_assets(model_dir, cfg_path)

    standard_text_value = resolve_standard_text(target_language, standard_text)
    char_count = count_chars(standard_text_value)
    if char_count <= 0:
        raise ValueError(
            f"Invalid standard text for char counting: {standard_text_value!r}. "
            "Provide --standard-text with non-empty non-punctuation content."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    cloned_dir = output_dir / "cloned"
    cloned_dir.mkdir(parents=True, exist_ok=True)

    tts = build_tts(
        index_tts_dir=index_tts_dir,
        model_dir=model_dir,
        cfg_path=cfg_path,
        use_fp16=use_fp16,
        use_cuda_kernel=use_cuda_kernel,
        use_deepspeed=use_deepspeed,
        auto_install_missing_deps=auto_install_missing_deps,
    )

    items: list[dict[str, Any]] = []
    speeds: list[float] = []
    source_speeds: list[float] = []
    failed = 0
    process_items = mapping if limit is None else mapping[:limit]

    for i, seg in enumerate(process_items):
        seg_id = int(seg.get("id", i + 1))
        ref_file = seg.get("file")
        if not ref_file:
            failed += 1
            items.append(
                {
                    "id": seg_id,
                    "status": "failed",
                    "failed_reason": "missing file in mapping entry",
                }
            )
            continue

        ref_path = (segments_dir / ref_file).resolve()
        cloned_file = f"segment_{seg_id:04d}.wav"
        cloned_path = cloned_dir / cloned_file
        source_text = str(seg.get("text", "")).strip()
        source_char_count = count_chars(source_text)
        source_duration_sec = segment_duration_from_mapping(seg)
        source_speed = (
            source_duration_sec / source_char_count
            if source_char_count > 0 and source_duration_sec > 0
            else None
        )
        if source_speed is not None:
            source_speeds.append(source_speed)

        if not ref_path.exists():
            failed += 1
            items.append(
                {
                    "id": seg_id,
                    "ref_file": ref_file,
                    "source_text": source_text,
                    "source_char_count": source_char_count,
                    "source_duration_sec": round(source_duration_sec, 4),
                    "source_speed_sec_per_char": round(source_speed, 4) if source_speed is not None else None,
                    "status": "failed",
                    "failed_reason": f"reference audio not found: {ref_path}",
                }
            )
            continue

        try:
            if not (skip_existing and cloned_path.exists()):
                tts.infer(
                    spk_audio_prompt=str(ref_path),
                    text=standard_text_value,
                    output_path=str(cloned_path),
                    verbose=False,
                )
            duration = float(sf.info(str(cloned_path)).duration)
            speed = duration / char_count
            speeds.append(speed)
            items.append(
                {
                    "id": seg_id,
                    "ref_file": ref_file,
                    "cloned_file": str(Path("cloned") / cloned_file),
                    "target_language": target_language,
                    "standard_text": standard_text_value,
                    "char_count": char_count,
                    "source_text": source_text,
                    "source_char_count": source_char_count,
                    "source_duration_sec": round(source_duration_sec, 4),
                    "source_speed_sec_per_char": round(source_speed, 4) if source_speed is not None else None,
                    "cloned_duration_sec": round(duration, 4),
                    "speed_sec_per_char": round(speed, 4),
                    "status": "success",
                }
            )
        except Exception as exc:
            failed += 1
            items.append(
                {
                    "id": seg_id,
                    "ref_file": ref_file,
                    "cloned_file": str(Path("cloned") / cloned_file),
                    "target_language": target_language,
                    "standard_text": standard_text_value,
                    "char_count": char_count,
                    "source_text": source_text,
                    "source_char_count": source_char_count,
                    "source_duration_sec": round(source_duration_sec, 4),
                    "source_speed_sec_per_char": round(source_speed, 4) if source_speed is not None else None,
                    "status": "failed",
                    "failed_reason": str(exc),
                }
            )

    summary = {
        "target_language": target_language,
        "standard_text": standard_text_value,
        "segments_total": len(process_items),
        "segments_success": len(process_items) - failed,
        "segments_failed": failed,
        "source_avg_speed_sec_per_char": round(sum(source_speeds) / len(source_speeds), 4) if source_speeds else 0.0,
        "source_median_speed_sec_per_char": round(statistics.median(source_speeds), 4) if source_speeds else 0.0,
        "source_p90_speed_sec_per_char": round(percentile(source_speeds, 0.9), 4) if source_speeds else 0.0,
        "avg_speed_sec_per_char": round(sum(speeds) / len(speeds), 4) if speeds else 0.0,
        "median_speed_sec_per_char": round(statistics.median(speeds), 4) if speeds else 0.0,
        "p90_speed_sec_per_char": round(percentile(speeds, 0.9), 4) if speeds else 0.0,
    }

    mapping_out = output_dir / "speed_mapping.json"
    summary_out = output_dir / "speed_summary.json"
    with open(mapping_out, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    with open(summary_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return {
        "mapping_out": mapping_out,
        "summary_out": summary_out,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="基于 index-TTS2 复刻标准语并计算语速（秒/字）"
    )
    parser.add_argument(
        "--mapping",
        default=None,
        help="mapping.json 路径（通常为 output/<剧名>/<视频名>/segments/mapping.json）",
    )
    parser.add_argument(
        "--video-output-dir",
        default=None,
        help="可选，视频输出目录（包含 segments/）；传入后可自动推断 mapping 与默认输出目录",
    )
    parser.add_argument(
        "--segments-dir",
        default=None,
        help="segments 目录路径，默认使用 mapping.json 所在目录",
    )
    parser.add_argument(
        "--segmentals-dir",
        dest="segments_dir",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--target-language",
        default=None,
        help="目标语言（单个），如 zh/en/ja",
    )
    parser.add_argument(
        "--target-languages",
        nargs="+",
        default=None,
        help="目标语言列表（多个），如 zh en ja",
    )
    parser.add_argument(
        "--standard-text",
        default=None,
        help="可选，覆盖默认标准语文本（例如 zh 默认'你好'，en 默认'hello world'）",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="语速输出目录，默认 output/<剧名>/<视频名>/speed_profile",
    )
    parser.add_argument(
        "--index-tts-dir",
        default=str(VENDORS_DIR / "index-tts"),
        help="index-tts 仓库目录，默认 scripts/vendors/index-tts",
    )
    parser.add_argument("--model-dir", default=None, help="index-tts checkpoints 目录")
    parser.add_argument("--cfg-path", default=None, help="index-tts config.yaml 路径")
    parser.add_argument(
        "--clone-index-tts",
        action="store_true",
        help="index-tts 缺失时自动克隆到 --index-tts-dir（建议 scripts/vendors/index-tts）",
    )
    parser.add_argument(
        "--git-lfs-pull",
        action="store_true",
        help="自动执行 git lfs install && git lfs pull（通常用于下载大模型）",
    )
    parser.add_argument(
        "--git-lfs-pull~",
        dest="git_lfs_pull",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--use-fp16", action="store_true", help="启用 FP16 推理")
    parser.add_argument("--use-cuda-kernel", action="store_true", help="启用 CUDA kernel 加速")
    parser.add_argument("--use-deepspeed", action="store_true", help="启用 deepspeed")
    parser.add_argument(
        "--auto-install-missing-deps",
        action="store_true",
        help="自动 pip 安装导入 IndexTTS2 时缺失的依赖（如 json5）",
    )
    parser.add_argument("--no-skip-existing", action="store_true", help="已存在复刻音频时强制重跑")
    parser.add_argument("--limit", type=int, default=None, help="仅处理前 N 个片段（调试用）")
    parser.add_argument(
        "--lang-workers",
        type=int,
        default=1,
        help="多语言并发数（仅在 --target-languages 生效，默认 1）",
    )
    args = parser.parse_args()

    languages: list[str] = []
    if args.target_language:
        languages.append(str(args.target_language).strip())
    if args.target_languages:
        languages.extend(str(x).strip() for x in args.target_languages if str(x).strip())
    # 去重并保持顺序
    deduped_languages: list[str] = []
    seen_langs: set[str] = set()
    for lang in languages:
        if lang not in seen_langs:
            deduped_languages.append(lang)
            seen_langs.add(lang)
    languages = deduped_languages
    if not languages:
        print("错误: --target-language 或 --target-languages 至少需要提供一个")
        return 1

    if not args.mapping and not args.video_output_dir:
        print("错误: --mapping 和 --video-output-dir 至少需要提供一个")
        return 1

    if args.mapping:
        mapping_path = Path(args.mapping).resolve()
    else:
        mapping_path = (Path(args.video_output_dir).resolve() / "segments" / "mapping.json").resolve()
    if not mapping_path.exists():
        print(f"错误: mapping.json 未找到: {mapping_path}")
        return 1

    segments_dir = (
        Path(args.segments_dir).resolve()
        if args.segments_dir
        else mapping_path.parent.resolve()
    )
    if not segments_dir.exists():
        print(f"错误: segments 目录未找到: {segments_dir}")
        return 1

    base_output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else mapping_path.parent.parent / "speed_profile"
    )

    try:
        def _run_one_language(lang: str) -> tuple[str, dict[str, Any] | None, str | None]:
            # 单语言兼容历史目录，多语言输出到 speed_profile/<lang>/
            out_dir = base_output_dir if len(languages) == 1 else base_output_dir / lang
            try:
                result = run(
                    mapping_path=mapping_path,
                    segments_dir=segments_dir,
                    output_dir=out_dir,
                    target_language=lang,
                    standard_text=args.standard_text,
                    index_tts_dir=Path(args.index_tts_dir).resolve(),
                    model_dir=Path(args.model_dir).resolve() if args.model_dir else None,
                    cfg_path=Path(args.cfg_path).resolve() if args.cfg_path else None,
                    clone_index_tts=args.clone_index_tts,
                    git_lfs_pull=args.git_lfs_pull,
                    use_fp16=args.use_fp16,
                    use_cuda_kernel=args.use_cuda_kernel,
                    use_deepspeed=args.use_deepspeed,
                    auto_install_missing_deps=args.auto_install_missing_deps,
                    skip_existing=not args.no_skip_existing,
                    limit=args.limit,
                )
                return lang, result, None
            except Exception as exc:
                return lang, None, str(exc)

        results: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        lang_workers = max(1, min(args.lang_workers, len(languages)))
        if len(languages) == 1 or lang_workers == 1:
            for lang in languages:
                l, r, err = _run_one_language(lang)
                if err:
                    errors[l] = err
                elif r is not None:
                    results[l] = r
        else:
            with ThreadPoolExecutor(max_workers=lang_workers) as executor:
                futures = [executor.submit(_run_one_language, lang) for lang in languages]
                for fut in as_completed(futures):
                    lang, result, err = fut.result()
                    if err:
                        errors[lang] = err
                    elif result is not None:
                        results[lang] = result

        print("================================================")
        for lang in languages:
            if lang in errors:
                print(f"[{lang}] 失败: {errors[lang]}")
                continue
            result = results[lang]
            print(f"[{lang}] 完成: {result['mapping_out']}")
            print(f"[{lang}] 完成: {result['summary_out']}")
            print(f"[{lang}] 汇总: {json.dumps(result['summary'], ensure_ascii=False)}")
        print("================================================")
        if errors:
            print(f"错误: 共 {len(errors)} 个语言评估失败，已输出其余语言结果。")
            return 1
        return 0
    except Exception as exc:
        print(f"错误: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
