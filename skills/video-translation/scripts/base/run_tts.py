#!/usr/bin/env python3
"""
Run Index-TTS to clone voices using translated transcripts.
Input:
- transcript_{lang}.json
- segments/mapping.json
- segments directory
Output:
- tts/{lang}/segment_XXXX.wav
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

import soundfile as sf
import yaml

# Add scripts/vendors/index-tts to path if needed, similar to count_speed_profile.py
SCRIPT_DIR = Path(__file__).resolve().parent
TRANSLATE_VIDEO_ROOT = SCRIPT_DIR.parent.parent
VENDORS_DIR = TRANSLATE_VIDEO_ROOT / "scripts" / "vendors"

def validate_model_assets(model_dir: Path, cfg_path: Path) -> None:
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
            candidate_tokenizer_files = [
                qwen_dir / "tokenizer.json",
                qwen_dir / "tokenizer_config.json",
            ]
            if not any(p.exists() for p in candidate_tokenizer_files):
                missing.append(
                    f"{qwen_dir} (missing tokenizer files)"
                )

    if missing:
        raise FileNotFoundError(f"Missing assets: {missing}")

def build_tts(
    index_tts_dir: Path,
    model_dir: Path,
    cfg_path: Path,
    use_fp16: bool,
    use_cuda_kernel: bool,
    use_deepspeed: bool,
):
    sys.path.insert(0, str(index_tts_dir))
    try:
        from indextts.infer_v2 import IndexTTS2
    except ImportError as e:
        raise RuntimeError(f"Failed to import IndexTTS2: {e}")

    return IndexTTS2(
        cfg_path=str(cfg_path),
        model_dir=str(model_dir),
        use_fp16=use_fp16,
        use_cuda_kernel=use_cuda_kernel,
        use_deepspeed=use_deepspeed,
    )


def segment_target_duration(mapping_item: dict[str, Any]) -> float:
    try:
        if "duration" in mapping_item:
            return max(0.0, float(mapping_item["duration"]))
        start = float(mapping_item.get("start", 0.0))
        end = float(mapping_item.get("end", start))
        return max(0.0, end - start)
    except Exception:
        return 0.0


def finalize_tts_audio(
    src_audio: Path,
    dst_audio: Path,
    target_duration: float,
    pad_to_target: bool,
) -> float:
    info = sf.info(str(src_audio))
    current_duration = float(info.duration)
    target_duration = max(0.0, float(target_duration))
    if target_duration <= 0 or not pad_to_target or current_duration >= target_duration:
        if src_audio != dst_audio:
            src_audio.replace(dst_audio)
        return current_duration

    # Small drift tolerance to avoid unnecessary re-encoding.
    if abs(current_duration - target_duration) <= 0.03:
        if src_audio != dst_audio:
            src_audio.replace(dst_audio)
        return current_duration

    # Scheme C: no speed-up/no trimming in TTS stage; optional tail silence padding only.
    af = f"apad=pad_dur={target_duration:.6f},atrim=0:{target_duration:.6f}"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src_audio),
        "-af",
        af,
        str(dst_audio),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg duration align failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return float(sf.info(str(dst_audio)).duration)

def run(
    transcript_path: Path,
    mapping_path: Path,
    segments_dir: Path,
    output_dir: Path,
    index_tts_dir: Path | None = None,
    model_dir: Path | None = None,
    cfg_path: Path | None = None,
    use_fp16: bool = False,
    use_cuda_kernel: bool = False,
    use_deepspeed: bool = False,
    skip_existing: bool = True,
    pad_to_target: bool = False,
):
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript_data = json.load(f)
    
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping_data = json.load(f)
    
    # Create a lookup for mapping by ID
    mapping_dict = {item["id"]: item for item in mapping_data}
    
    index_tts_dir = (index_tts_dir or (VENDORS_DIR / "index-tts")).resolve()
    model_dir = (model_dir or (index_tts_dir / "checkpoints")).resolve()
    cfg_path = (cfg_path or (model_dir / "config.yaml")).resolve()
    
    validate_model_assets(model_dir, cfg_path)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tts = build_tts(
        index_tts_dir=index_tts_dir,
        model_dir=model_dir,
        cfg_path=cfg_path,
        use_fp16=use_fp16,
        use_cuda_kernel=use_cuda_kernel,
        use_deepspeed=use_deepspeed,
    )
    
    results = []
    failed_count = 0
    
    segments = transcript_data.get("segments", [])
    for seg in segments:
        seg_id = seg["id"]
        text = seg["text"]
        
        mapping_item = mapping_dict.get(seg_id)
        if not mapping_item:
            print(f"Warning: Segment {seg_id} not found in mapping.json")
            continue
            
        ref_file = mapping_item["file"]
        ref_path = segments_dir / ref_file
        
        if not ref_path.exists():
            print(f"Warning: Reference audio not found: {ref_path}")
            failed_count += 1
            continue
            
        # Output filename same as input segment filename but in tts dir
        # or use segment_id
        out_filename = f"segment_{seg_id:04d}.wav"
        out_path = output_dir / out_filename
        target_duration = segment_target_duration(mapping_item)
        
        if skip_existing and out_path.exists():
            print(f"Skipping existing: {out_path}")
            results.append({"id": seg_id, "status": "skipped", "file": str(out_path)})
            continue
            
        print(f"Processing {seg_id}: {text}")
        try:
            with tempfile.TemporaryDirectory(prefix=f"tts_seg_{seg_id:04d}_") as td:
                raw_out_path = Path(td) / "raw.wav"
                tts.infer(
                    spk_audio_prompt=str(ref_path),
                    text=text,
                    output_path=str(raw_out_path),
                    verbose=False,
                )
                final_duration = finalize_tts_audio(
                    raw_out_path,
                    out_path,
                    target_duration,
                    pad_to_target=pad_to_target,
                )
            results.append(
                {
                    "id": seg_id,
                    "status": "success",
                    "file": str(out_path),
                    "target_duration_sec": round(target_duration, 4),
                    "actual_duration_sec": round(final_duration, 4),
                }
            )
        except Exception as e:
            print(f"Error processing {seg_id}: {e}")
            traceback.print_exc()
            failed_count += 1
            results.append({"id": seg_id, "status": "failed", "error": str(e)})
            
    # Write summary
    summary_path = output_dir / "tts_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"TTS finished. Success: {len(segments) - failed_count}, Failed: {failed_count}")
    return 0 if failed_count == 0 else 1

def main():
    parser = argparse.ArgumentParser(description="Run Index-TTS for translation")
    parser.add_argument("--transcript-path", required=True)
    parser.add_argument("--mapping-path", required=True)
    parser.add_argument("--segments-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--index-tts-dir", default=str(VENDORS_DIR / "index-tts"))
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--cfg-path", default=None)
    parser.add_argument("--use-fp16", action="store_true")
    parser.add_argument("--use-cuda-kernel", action="store_true")
    parser.add_argument("--use-deepspeed", action="store_true")
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument(
        "--pad-to-target",
        action="store_true",
        help="仅在生成音频短于目标时长时补尾部静音；不会进行倍速或裁剪",
    )
    
    args = parser.parse_args()
    
    return run(
        transcript_path=Path(args.transcript_path),
        mapping_path=Path(args.mapping_path),
        segments_dir=Path(args.segments_dir),
        output_dir=Path(args.output_dir),
        index_tts_dir=Path(args.index_tts_dir),
        model_dir=Path(args.model_dir) if args.model_dir else None,
        cfg_path=Path(args.cfg_path) if args.cfg_path else None,
        use_fp16=args.use_fp16,
        use_cuda_kernel=args.use_cuda_kernel,
        use_deepspeed=args.use_deepspeed,
        skip_existing=not args.no_skip_existing,
        pad_to_target=args.pad_to_target,
    )

if __name__ == "__main__":
    sys.exit(main())
