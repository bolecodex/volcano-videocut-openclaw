#!/usr/bin/env python3
"""
poll_media.py — 重启媒体类任务轮询

用法:
  python <SKILL_DIR>/scripts/poll_media.py <task_type> <RunId> [space_name]

task_type 取值：
  voiceSeparation / audioNoiseReduction /
  enhanceVideo / videSuperResolution / videoInterlacing
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import ensure_deps, load_credentials, build_service, get_space_name, poll_media, out, bail

def main():
    if len(sys.argv) < 3:
        bail("用法: python <SKILL_DIR>/scripts/poll_media.py <task_type> <RunId> [space_name]")
    task_type = sys.argv[1]
    run_id    = sys.argv[2]
    ensure_deps()
    ak, sk = load_credentials()
    client = build_service(ak, sk)
    space_name = get_space_name(argv_pos=3)
    result = poll_media(client, task_type, run_id, space_name)
    out(result)

if __name__ == "__main__":
    main()
