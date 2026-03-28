import argparse
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path

import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")


class VolcEngineApiClient:
    def __init__(self, ak: str, sk: str, region="cn-beijing", service="imagination"):
        self.ak, self.sk, self.region, self.service = ak, sk, region, service

    def request(self, action: str, body: dict, method="POST") -> str:
        url = f"http://open.volcengineapi.com/?Action={action}&Version=2024-08-12"
        json_body = "" if method == "GET" else json.dumps(body, ensure_ascii=False)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bh = hashlib.sha256(json_body.encode()).hexdigest()

        h = {"content-type": "application/json; charset=utf-8", "host": "open.volcengineapi.com",
             "x-content-sha256": bh, "x-date": ts}
        sk_list = sorted(h.keys())
        ch, sh = "".join(f"{k}:{h[k]}\n" for k in sk_list), ";".join(sk_list)
        cr = f"{method}\n/\nAction={action}&Version=2024-08-12\n{ch}\n{sh}\n{bh}"

        cs = f"{ts[:8]}/{self.region}/{self.service}/request"
        sts = f"HMAC-SHA256\n{ts}\n{cs}\n{hashlib.sha256(cr.encode()).hexdigest()}"
        sig = hmac.new(reduce(lambda k, v: hmac.new(k, v.encode(), hashlib.sha256).digest(),
                              [ts[:8], self.region, self.service, "request"], self.sk.encode()),
                       sts.encode(), hashlib.sha256).hexdigest()

        headers = {k.title().replace("X-C", "X-c"): v for k, v in h.items()}
        headers["Authorization"] = f"HMAC-SHA256 Credential={self.ak}/{cs}, SignedHeaders={sh}, Signature={sig}"

        r = (requests.get if method == "GET" else requests.post)(url, headers=headers,
                                                                 data=json_body.encode() if method == "POST" else None)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}: {r.text}")
        return r.text

    def generate_song(self, prompt: str = "", **kwargs) -> str:
        body = {
            "ModelVersion": kwargs.get("ModelVersion", "v4.3"),
            "Genre": kwargs.get("Genre", "Pop"),
            "Mood": kwargs.get("Mood", "Nostalgic/Memory"),
            "Gender": kwargs.get("Gender", "Male"),
            "Timbre": kwargs.get("Timbre", "Husky"),
            "Duration": kwargs.get("Duration", 60),
            "SkipCopyCheck": kwargs.get("SkipCopyCheck", False),
        }

        if prompt:
            body["Prompt"] = prompt

        if kwargs.get("Lyrics"):
            body["Lyrics"] = kwargs["Lyrics"]

        response_text = self.request("GenSongV4", body)
        response = json.loads(response_text)
        print(f"Full response: {json.dumps(response, ensure_ascii=False, indent=2)}")
        result = response.get("Result", {})
        task_id = result.get("TaskID") if result else None

        if not task_id:
            raise Exception(f"Failed to get TaskID: {json.dumps(response, ensure_ascii=False)}")

        return task_id

    def query_job(self, task_id: str) -> dict:
        body = {"TaskID": task_id}
        response_text = self.request("QuerySong", body)
        return json.loads(response_text)

    def poll_job(self, task_id: str, max_attempts: int = 120, interval: int = 5) -> str:
        for i in range(max_attempts):
            response = self.query_job(task_id)
            result = response.get("Result", {})
            status = result.get("Status")
            progress = result.get("Progress", 0)

            print(f"Polling {i + 1}/{max_attempts}: Status={status}, Progress={progress}%")

            if status == 2:
                song_detail = result.get("SongDetail", {})
                audio_url = song_detail.get("AudioUrl")
                if audio_url:
                    return audio_url
                raise Exception("Task succeeded but AudioUrl not found")
            elif status == 3:
                failure_reason = result.get("FailureReason", {})
                code = failure_reason.get("Code")
                msg = failure_reason.get("Msg")
                raise Exception(f"Task failed: Code={code}, Msg={msg}")
            elif status in [0, 1]:
                time.sleep(interval)
            else:
                raise Exception(f"Unknown status: {status}")

        raise Exception(f"Polling timeout after {max_attempts} attempts")


def main():
    """
    通用 CLI 入口，适配 Skill 编排与本地调试。

    - 所有业务参数（prompt、歌词、风格等）由上游意图识别/编排层动态传入；
      本脚本只负责「提交任务」与「查询任务」。
    - 通过 `--mode` 控制行为：
        - submit：仅提交任务，返回 TaskID；
        - poll：仅根据 TaskID 轮询任务结果。

    示例（在 Skill 根目录 ./music-generate 下，使用 uv 启动，路径相对 Skill 根目录）：

    提交任务：
        uv run python ./scripts/music_project/main.py \\
          --mode submit \\
          --lyrics-file lyrics_xiaoyezu.txt \\
          --genre "Rock,Alternative Rock,Hard Rock" \\
          --mood "Sorrow/Sad,Sentimental/Melancholic/Lonely" \\
          --gender "Male" \\
          --timbre "Husky,Deep,Gentle" \\
          --duration 120 \\
          --model-version v4.3

    查询任务：
        uv run python ./scripts/music_project/main.py \\
          --mode poll \\
          --task-id YOUR_TASK_ID
    """
    parser = argparse.ArgumentParser(description="GenSongV4 music_project CLI")

    parser.add_argument(
        "--mode",
        choices=["submit", "poll"],
        default="submit",
        help="执行模式：submit=提交生成任务，仅返回 TaskID；poll=仅根据 TaskID 轮询任务结果。",
    )

    # 提交任务相关参数（全部由上游意图识别后动态传入）
    parser.add_argument(
        "--lyrics-file",
        type=str,
        default=None,
        help="歌词文件路径；submit 模式下必填。",
    )
    parser.add_argument(
        "--model-version",
        type=str,
        default="v4.3",
        help="模型版本，如 v4.0 / v4.3（上游可根据策略动态选择）。",
    )
    parser.add_argument(
        "--genre",
        type=str,
        default="Pop",
        help="风格标签，如 'Pop'、'Rock,Alternative Rock,Hard Rock' 等。",
    )
    parser.add_argument(
        "--mood",
        type=str,
        default="Nostalgic/Memory",
        help="情绪标签，由意图识别阶段填充。",
    )
    parser.add_argument(
        "--gender",
        type=str,
        default="Male",
        help="演唱性别，如 'Male' 或 'Female'。",
    )
    parser.add_argument(
        "--timbre",
        type=str,
        default="Husky",
        help="音色描述，如 'Husky,Deep,Gentle'。",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="歌曲时长（秒），由意图识别阶段给出。",
    )
    parser.add_argument(
        "--skip-copy-check",
        action="store_true",
        help="是否跳过版权检测，上游可根据业务需要决定是否传入该标记。",
    )

    # 查询任务相关参数
    parser.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="已有任务的 TaskID，仅在 --mode poll 时必填。",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=120,
        help="轮询最大次数（仅 poll 模式有效）。",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="轮询间隔秒数（仅 poll 模式有效）。",
    )

    args = parser.parse_args()

    ak = os.getenv("VOLC_ACCESS_KEY_ID")
    sk = os.getenv("VOLC_ACCESS_KEY_SECRET")
    region = os.getenv("VOLC_REGION", "cn-beijing")
    service = os.getenv("VOLC_SERVICE", "imagination")

    if not ak or not sk:
        raise RuntimeError("请先在环境变量中配置 VOLC_ACCESS_KEY_ID 和 VOLC_ACCESS_KEY_SECRET。")

    client = VolcEngineApiClient(ak, sk, region, service)

    # --- 模式一：仅提交任务 ---
    if args.mode == "submit":
        if not args.lyrics_file:
            raise ValueError("提交任务时必须通过 --lyrics-file 提供歌词文件路径。")

        lyrics_path = Path(args.lyrics_file)
        if not lyrics_path.is_absolute():
            lyrics_path = Path.cwd() / lyrics_path

        if not lyrics_path.exists():
            raise FileNotFoundError(f"未找到歌词文件：{lyrics_path}")

        with open(lyrics_path, "r", encoding="utf-8") as f:
            lyrics = f.read()

        print("Submitting GenSongV4 task...")
        task_id = client.generate_song(
            Lyrics=lyrics,
            Genre=args.genre,
            Mood=args.mood,
            Gender=args.gender,
            Timbre=args.timbre,
            Duration=args.duration,
            ModelVersion=args.model_version,
            SkipCopyCheck=bool(args.skip_copy_check),
        )
        # 方便 Skill 编排消费：仅输出 TaskID 一行即可被上游解析
        print(f"TaskID={task_id}")
        return

    # --- 模式二：仅查询任务 ---
    if args.mode == "poll":
        if not args.task_id:
            raise ValueError("轮询任务时必须通过 --task-id 提供 TaskID。")

        print(f"Polling task {args.task_id} ...")
        audio_url = client.poll_job(
            task_id=args.task_id,
            max_attempts=args.max_attempts,
            interval=args.interval,
        )
        # 同样输出单行结果，便于编排层解析
        print(f"AudioUrl={audio_url}")
        return


if __name__ == "__main__":
    main()
