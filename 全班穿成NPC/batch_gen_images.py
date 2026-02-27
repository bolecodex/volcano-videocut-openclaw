#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成前5个场景的分镜图片
通过 MCP/API 调用 Seedream 4.5
已生成 4 张，剩余 106 张需继续运行

用法：在 Cursor 中执行 /novel-04-shots-to-images 并选择场景，
      或手动调用本脚本（需配置 API）
"""

import yaml
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
SHOTS_DIR = PROJECT_DIR / "shots"
SCENES = ["SC_01_开篇旁白", "SC_02_殿内白绫", "SC_03_朝露殿冷宫", "SC_04_林燕容来访", "SC_05_周鹏夜送饭"]

def count_pending():
    total, pending = 0, 0
    for name in SCENES:
        path = SHOTS_DIR / f"{name}.yaml"
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for s in data.get("shots", []):
            total += 1
            if s.get("image_status") != "completed":
                pending += 1
    return total, pending

if __name__ == "__main__":
    total, pending = count_pending()
    print(f"前5场景：共 {total} 张，已完成 {total - pending} 张，待生成 {pending} 张")
    print("继续生成请使用: /novel-04-shots-to-images 并选择 SC_01 至 SC_05")
