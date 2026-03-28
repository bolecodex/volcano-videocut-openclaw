#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import threading
import time
import traceback
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import ffmpeg

from asr_qwen import transcribe_audio
from av_separation import (
    run_mute_video as av_run_mute_video,
    run_voice_background_separation as av_run_voice_background_separation,
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".flv", ".wmv", ".webm", ".m4v", ".ts"}
STAGES = ["prepare_original", "extract_audio", "mute_video", "separate", "asr"]
MAX_CONCURRENCY = 5
MAX_QUEUE_SIZE = 5


@dataclass
class PipelineError(Exception):
    code: str
    stage: str
    message: str
    detail: str = ""
    suggestion: str = ""
    retryable: bool = True


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class ProgressTracker:
    def __init__(self, total: int, mode: str):
        self.total = total
        self.mode = mode
        self.lock = threading.Lock()
        self.queued = total
        self.running = 0
        self.done = 0
        self.success = 0
        self.failed = 0

    def p(self, msg: str) -> None:
        print(msg, flush=True)

    def batch(self) -> None:
        self.p(
            f"[Batch] total={self.total} running={self.running} queued={self.queued} "
            f"done={self.done} success={self.success} failed={self.failed}"
        )

    def task_start(self, tid: str) -> None:
        with self.lock:
            self.queued -= 1
            self.running += 1
            self.p(f"[{tid}] START")
            self.batch()

    def task_end(self, tid: str, ok: bool, cost: float) -> None:
        with self.lock:
            self.running -= 1
            self.done += 1
            if ok:
                self.success += 1
                self.p(f"[{tid}] DONE ({cost:.1f}s)")
            else:
                self.failed += 1
                self.p(f"[{tid}] FAILED ({cost:.1f}s)")
            self.batch()

    def stage_start(self, tid: str, stage: str, attempt: int, total: int, detail: str = "") -> None:
        msg = f"[{tid}] {stage} START attempt={attempt}/{total}"
        if self.mode == "verbose" and detail:
            msg += f" | {detail}"
        self.p(msg)

    def stage_ok(self, tid: str, stage: str, cost: float) -> None:
        self.p(f"[{tid}] {stage} OK ({cost:.1f}s)")

    def retry(self, tid: str, stage: str, next_attempt: int, total: int, err: PipelineError) -> None:
        self.p(f"[{tid}] {stage} RETRY {next_attempt}/{total} code={err.code} reason={err.message}")
        if self.mode == "verbose" and err.detail:
            self.p(f"[{tid}] {stage} detail={err.detail}")

    def fail(self, tid: str, stage: str, err: PipelineError) -> None:
        self.p(f"[{tid}] {stage} FAIL code={err.code} message={err.message}")
        if err.detail:
            self.p(f"[{tid}] {stage} detail={err.detail}")
        if err.suggestion:
            self.p(f"[{tid}] {stage} suggestion={err.suggestion}")


def build_error(stage: str, exc: BaseException) -> PipelineError:
    if isinstance(exc, PipelineError):
        return exc
    if isinstance(exc, ffmpeg.Error):
        stderr = ""
        try:
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else str(exc)
        except Exception:
            stderr = str(exc)
        code = {
            "prepare_original": "FFMPEG_REPACK_FAILED",
            "extract_audio": "FFMPEG_EXTRACT_FAILED",
            "mute_video": "FFMPEG_MUTE_FAILED",
        }.get(stage, "FFMPEG_FAILED")
        return PipelineError(code, stage, f"{stage} 阶段执行失败（FFmpeg）", stderr[:4000], "请检查 ffmpeg 与输入文件。")
    if isinstance(exc, SystemExit):
        return PipelineError("ASR_MODEL_LOAD_FAILED" if stage == "asr" else "INTERNAL_ERROR", stage, f"{stage} 阶段异常退出", f"SystemExit: {exc}", "检查模型依赖和设备参数。")
    detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    code = {"separate": "DEMUCS_FAILED", "asr": "ASR_TRANSCRIBE_FAILED"}.get(stage, "INTERNAL_ERROR")
    if stage == "extract_audio":
        code = "FFMPEG_EXTRACT_FAILED"
    if stage == "mute_video":
        code = "FFMPEG_MUTE_FAILED"
    if stage == "prepare_original":
        code = "OUTPUT_WRITE_FAILED"
    return PipelineError(code, stage, f"{stage} 阶段执行失败", detail, "查看 detail 定位具体原因。")


def stage_percent(stage: str) -> int:
    return int((STAGES.index(stage) + 1) / len(STAGES) * 100)


def safe_name(name: str) -> str:
    x = "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_")
    return x or "video"


def is_url(value: str) -> bool:
    u = urllib.parse.urlparse(value)
    return u.scheme in {"http", "https"} and bool(u.netloc)


def collect_tasks(input_values: list[str]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    dir_inputs: list[Path] = []

    for input_value in input_values:
        if is_url(input_value):
            # 优先使用 URL 解码后的真实文件名（例如 raw%2F...%2F3_wCzk.mp4 -> 3_wCzk.mp4）
            path = urllib.parse.unquote(urllib.parse.urlparse(input_value).path)
            tasks.append(
                {
                    "kind": "url",
                    "source": input_value,
                    "name": safe_name(Path(path).stem or "remote_video"),
                }
            )
            continue

        p = Path(input_value).resolve()
        if not p.exists():
            raise PipelineError("INPUT_NOT_FOUND", "prepare_input", "输入路径不存在", str(p), "请检查输入路径。", False)

        if p.is_dir():
            dir_inputs.append(p)
            if len(dir_inputs) > 1:
                raise PipelineError(
                    "INPUT_INVALID",
                    "prepare_input",
                    "批量输入时最多只允许一个文件夹路径",
                    ", ".join(str(x) for x in dir_inputs),
                    "请保留一个文件夹，其他输入请使用文件路径或链接。",
                    False,
                )
            videos = sorted([x.resolve() for x in p.rglob("*") if x.is_file() and x.suffix.lower() in VIDEO_EXTENSIONS])
            if not videos:
                raise PipelineError("INPUT_NOT_FOUND", "prepare_input", "目录下未找到视频文件", str(p), "请确认目录内存在视频。", False)
            for v in videos:
                tasks.append({"kind": "file", "source": str(v), "path": v, "name": safe_name(v.stem)})
            continue

        if p.suffix.lower() not in VIDEO_EXTENSIONS:
            raise PipelineError("INPUT_UNSUPPORTED", "prepare_input", "输入文件格式不支持", str(p), "请使用常见视频格式。", False)
        tasks.append({"kind": "file", "source": str(p), "path": p, "name": safe_name(p.stem)})

    # 同名任务保留最后一次输入，执行时会删除旧目录后重建（后者覆盖前者）
    dedup_by_name: dict[str, dict[str, Any]] = {}
    ordered_names: list[str] = []
    for task in tasks:
        name = task["name"]
        if name not in dedup_by_name:
            ordered_names.append(name)
        dedup_by_name[name] = task

    return [dedup_by_name[name] for name in ordered_names]


def download_video(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            with open(target, "wb") as f:
                shutil.copyfileobj(resp, f)
    except Exception as exc:
        raise PipelineError("DOWNLOAD_FAILED", "prepare_input", "视频下载失败", f"url={url} err={exc}", "请检查 URL 和网络。") from exc
    return target


def export_original(input_file: Path, output_mp4: Path) -> Path:
    try:
        ffmpeg.input(str(input_file)).output(str(output_mp4), vcodec="copy", acodec="copy").run(quiet=True, overwrite_output=True)
    except ffmpeg.Error:
        ffmpeg.input(str(input_file)).output(str(output_mp4), vcodec="libx264", acodec="aac", preset="veryfast", crf=23).run(quiet=True, overwrite_output=True)
    return output_mp4


def extract_audio(input_file: Path, out_mp3: Path) -> Path:
    ffmpeg.input(str(input_file)).output(str(out_mp3), format="mp3", acodec="libmp3lame", qscale="2").run(quiet=True, overwrite_output=True)
    return out_mp3


def mute_video(input_file: Path, out_mp4: Path) -> Path:
    return av_run_mute_video(input_file, out_mp4)


def separate_vocals_background(input_file: Path, out_dir: Path, vocals: Path, background: Path) -> tuple[Path, Path]:
    return av_run_voice_background_separation(input_file, out_dir, vocals, background)


def run_with_retry(task_id: str, stage: str, func, tracker: ProgressTracker, retry_times: int, backoff: float, detail: str = ""):
    last = None
    for attempt in range(1, retry_times + 1):
        tracker.stage_start(task_id, stage, attempt, retry_times, detail)
        t0 = time.time()
        try:
            ret = func()
            tracker.stage_ok(task_id, stage, time.time() - t0)
            return ret, round(time.time() - t0, 3)
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            err = build_error(stage, exc)
            last = err
            if attempt < retry_times and err.retryable:
                tracker.retry(task_id, stage, attempt + 1, retry_times, err)
                time.sleep(backoff * (2 ** (attempt - 1)))
                continue
            tracker.fail(task_id, stage, err)
            raise err
    raise last if last else PipelineError("INTERNAL_ERROR", stage, "未知错误")


def process_video(task: dict[str, Any], output_dir: Path, tracker: ProgressTracker, args) -> dict[str, Any]:
    task_id, source = task["name"], task["source"]
    status_path, lock = output_dir / "status.json", threading.Lock()
    status = {"task_id": task_id, "source": source, "status": "running", "current_stage": "", "attempt": 0, "progress_percent": 0, "started_at": now_iso(), "updated_at": now_iso(), "error": None, "outputs": {}, "stage_cost_seconds": {}}
    write_json(status_path, status)
    t0 = time.time()

    def save():
        status["updated_at"] = now_iso()
        with lock:
            write_json(status_path, status)

    files = {
        "original_video": output_dir / "original_video.mp4",
        "audio": output_dir / "audio.mp3",
        "muted_video": output_dir / "muted_video.mp4",
        "vocals": output_dir / "vocals.mp3",
        "background": output_dir / "background.mp3",
        "asr": output_dir / "asr.json",
    }

    try:
        local = download_video(source, output_dir / ".source_download.mp4") if task["kind"] == "url" else task["path"]
        for stage in STAGES:
            status["current_stage"], status["attempt"], status["progress_percent"] = stage, 1, stage_percent(stage)
            save()
            if stage == "prepare_original":
                _, c = run_with_retry(task_id, stage, lambda: export_original(local, files["original_video"]), tracker, args.retry_times, args.retry_backoff_base, f"in={local} out={files['original_video']}")
                status["outputs"]["original_video"] = str(files["original_video"])
            elif stage == "extract_audio":
                _, c = run_with_retry(task_id, stage, lambda: extract_audio(local, files["audio"]), tracker, args.retry_times, args.retry_backoff_base, f"out={files['audio']}")
                status["outputs"]["audio"] = str(files["audio"])
            elif stage == "mute_video":
                _, c = run_with_retry(task_id, stage, lambda: mute_video(local, files["muted_video"]), tracker, args.retry_times, args.retry_backoff_base, f"out={files['muted_video']}")
                status["outputs"]["muted_video"] = str(files["muted_video"])
            elif stage == "separate":
                _, c = run_with_retry(task_id, stage, lambda: separate_vocals_background(local, output_dir, files["vocals"], files["background"]), tracker, args.retry_times, args.retry_backoff_base, f"vocals={files['vocals']}")
                status["outputs"]["vocals"] = str(files["vocals"])
                status["outputs"]["background"] = str(files["background"])
            else:
                def run_asr():
                    data = transcribe_audio(str(files["vocals"]), model_size=args.asr_model, device=args.device, language=args.language)
                    write_json(files["asr"], data)
                    return files["asr"]

                _, c = run_with_retry(task_id, stage, run_asr, tracker, args.retry_times, args.retry_backoff_base, f"in={files['vocals']} out={files['asr']}")
                status["outputs"]["asr"] = str(files["asr"])
            status["stage_cost_seconds"][stage] = c
            save()

        status["status"] = "completed"
        status["progress_percent"] = 100
        status["cost_seconds"] = round(time.time() - t0, 3)
        save()
        return status
    except PipelineError as e:
        status["status"] = "failed"
        status["cost_seconds"] = round(time.time() - t0, 3)
        status["error"] = {"code": e.code, "stage": e.stage, "message": e.message, "detail": e.detail, "suggestion": e.suggestion, "retryable": e.retryable}
        save()
        return status


def worker(work_q: queue.Queue, results: list[dict[str, Any]], res_lock: threading.Lock, tracker: ProgressTracker, args, out_root: Path, series: str | None):
    while True:
        task = work_q.get()
        if task is None:
            work_q.task_done()
            return
        tid = task["name"]
        tracker.task_start(tid)
        t0 = time.time()
        out = out_root / series / tid if series else out_root / tid
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        try:
            result = process_video(task, out, tracker, args)
            ok = result.get("status") == "completed"
        except BaseException as exc:
            e = build_error("internal", exc)
            result = {"task_id": tid, "source": task["source"], "status": "failed", "error": {"code": e.code, "stage": e.stage, "message": e.message, "detail": e.detail, "suggestion": e.suggestion, "retryable": e.retryable}}
            ok = False
        tracker.task_end(tid, ok, time.time() - t0)
        with res_lock:
            results.append(result)
        work_q.task_done()


def parse_args():
    p = argparse.ArgumentParser(description="视频ASR流水线：静音、音视频分离、人声背景分离、ASR、批量并发")
    p.add_argument("input", nargs="+", help="输入：支持多个视频文件/https链接；文件夹路径最多一个")
    p.add_argument("--output-root", default="../../../../../output/", help="输出根目录（默认 video-translation 的父级的父级的父级 output）")
    p.add_argument("--series-name", default=None, help="剧集名（可选）")
    p.add_argument("--max-workers", type=int, default=5, help="并发数，最大5")
    p.add_argument("--queue-size", type=int, default=5, help="队列大小，最大5")
    p.add_argument("--retry-times", type=int, default=3, help="失败重试次数，默认3")
    p.add_argument("--retry-backoff-base", type=float, default=1.0, help="重试退避基数秒")
    p.add_argument("--asr-model", default="1.7B", help="ASR模型 0.6B/1.7B")
    p.add_argument("--device", default="auto", help="ASR设备 auto/cpu/cuda:0")
    p.add_argument("--language", default=None, help="ASR语言提示")
    p.add_argument("--log-mode", choices=["simple", "verbose"], default="simple", help="日志模式")
    p.add_argument("--verbose", action="store_true", help="等价于 --log-mode verbose")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.verbose:
        args.log_mode = "verbose"
    args.max_workers = max(1, min(args.max_workers, MAX_CONCURRENCY))
    args.queue_size = max(1, min(args.queue_size, MAX_QUEUE_SIZE))
    args.retry_times = max(1, args.retry_times)
    args.retry_backoff_base = max(0.1, args.retry_backoff_base)
    out_root = Path(args.output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    try:
        tasks = collect_tasks(args.input)
    except PipelineError as e:
        print(f"[FATAL] code={e.code} message={e.message}")
        if e.detail:
            print(f"[FATAL] detail={e.detail}")
        if e.suggestion:
            print(f"[FATAL] suggestion={e.suggestion}")
        return 1

    print("================================================")
    print("Video ASR Pipeline")
    print(f"input={args.input}")
    print(f"tasks={len(tasks)}")
    print(f"output_root={out_root}")
    print(f"series_name={args.series_name}")
    print(f"max_workers={args.max_workers} queue_size={args.queue_size}")
    print(f"retry_times={args.retry_times} backoff_base={args.retry_backoff_base}")
    print(f"log_mode={args.log_mode}")
    print("================================================")

    tracker = ProgressTracker(len(tasks), args.log_mode)
    work_q: queue.Queue = queue.Queue(maxsize=args.queue_size)
    results: list[dict[str, Any]] = []
    res_lock = threading.Lock()

    workers = []
    for _ in range(args.max_workers):
        t = threading.Thread(target=worker, args=(work_q, results, res_lock, tracker, args, out_root, args.series_name), daemon=True)
        t.start()
        workers.append(t)

    for task in tasks:
        work_q.put(task)
    for _ in workers:
        work_q.put(None)
    work_q.join()
    for t in workers:
        t.join()

    results.sort(key=lambda x: x.get("task_id", ""))
    success = sum(1 for x in results if x.get("status") == "completed")
    failed = len(results) - success
    report = {
        "finished_at": now_iso(),
        "input": args.input,
        "output_root": str(out_root),
        "series_name": args.series_name,
        "log_mode": args.log_mode,
        "retry_times": args.retry_times,
        "max_workers": args.max_workers,
        "queue_size": args.queue_size,
        "total": len(results),
        "success": success,
        "failed": failed,
        "tasks": results,
    }
    report_path = out_root / (args.series_name or "") / "pipeline_report.json"
    write_json(report_path, report)

    print("================================================")
    print(f"Pipeline finished: total={len(results)} success={success} failed={failed}")
    print(f"Report: {report_path}")
    print("================================================")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
