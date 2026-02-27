#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""novel-03: 场景转分镜 - 从 scenes/*.md 生成 shots/*.yaml 和 _manifest.yaml
用法: python gen_storyboard.py
"""

import re
import yaml
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent
SCENES_DIR = PROJECT_DIR / "scenes"
SHOTS_DIR = PROJECT_DIR / "shots"
STYLE_PATH = PROJECT_DIR / "style.yaml"
INDEX_PATH = PROJECT_DIR / "全班穿成NPC_场景索引.yaml"
CHAR_PATH = PROJECT_DIR / "全班穿成NPC_角色资产.yaml"

CHAR_ID = {
    "苏映雪": "@npc_suyingxue", "萧凌": "@npc_xiaoling", "林燕容": "@npc_linyanrong",
    "贤妃": "@npc_xianfei", "淑妃": "@npc_shufei", "太后": "@npc_taihou",
    "王浩": "@npc_wanghao", "李大壮": "@npc_lidazhuang", "李二壮": "@npc_lierzhuang",
    "张静": "@npc_zhangjing", "周鹏": "@npc_zhoupeng", "陈默": "@npc_chenmo",
    "刘胖子": "@npc_liupangzi", "赵磊": "@npc_zhaolei", "沈清瑶": "@npc_shenqingyao",
    "宣传委员": "@npc_xuanchuan",
}


def count_chars(text: str) -> int:
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff")


def parse_scene_file(path: Path) -> list:
    raw = path.read_text(encoding="utf-8")
    dialogs = []
    in_dialog = False
    for line in raw.split("\n"):
        if "## 对话内容" in line:
            in_dialog = True
            continue
        if not in_dialog:
            continue
        m = re.match(r"^([^：:]+)[：:]\s*(.*)$", line.strip())
        if m and m.group(2).strip():
            dialogs.append({"speaker": m.group(1).strip(), "text": m.group(2).strip()})
    return dialogs


def divide_into_shots(dialogs: list, max_chars: int = 28, min_chars: int = 12) -> list:
    shots, buf, buf_chars = [], [], 0
    for d in dialogs:
        c = count_chars(d["text"])
        if c > 28:
            if buf:
                shots.append(buf)
                buf, buf_chars = [], 0
            shots.append([d])
            continue
        if buf_chars + c <= max_chars:
            buf.append(d)
            buf_chars += c
        else:
            if buf:
                shots.append(buf)
            buf, buf_chars = [d], c
        if buf_chars >= min_chars and len(buf) >= 2 and buf_chars + 15 > max_chars:
            shots.append(buf)
            buf, buf_chars = [], 0
    if buf:
        shots.append(buf)
    return shots


def gen_prompt(shot_lines: list, scene_info: dict, style_base: str) -> str:
    speakers = set(l["speaker"] for l in shot_lines)
    char_refs = [f"{s}({CHAR_ID[s]})" for s in speakers if s in CHAR_ID and s != "旁白"]
    char_str = "，".join(char_refs) if char_refs else "古风人物"
    loc = scene_info.get("location", "宫廷室内")
    mood = scene_info.get("mood", "古风宫廷")
    return f"""{style_base}，{loc}，{mood}氛围，烛光或自然光，{char_str}，表情动作自然，中景镜头，三分构图，古风宫廷色调，高清细节"""


def main():
    style = yaml.safe_load(STYLE_PATH.read_text(encoding="utf-8")) if STYLE_PATH.exists() else {}
    style_base = style.get("style_base", "真人写实高清，超细节刻画，古风人像写实，光影细腻，宫廷华美色调")
    index = yaml.safe_load(INDEX_PATH.read_text(encoding="utf-8"))
    scenes_index = {s["id"]: s for s in index["scenes"]}
    SHOTS_DIR.mkdir(exist_ok=True)
    files_info, total_shots = [], 0

    for path in sorted(SCENES_DIR.glob("SC_*.md"), key=lambda p: int(p.stem.split("_")[1])):
        parts = path.stem.split("_", 2)
        sc_id, sc_name = f"{parts[0]}_{parts[1]}", parts[2] if len(parts) >= 3 else sc_id
        dialogs = parse_scene_file(path)
        if not dialogs:
            continue

        scene_info = scenes_index.get(sc_id, {})
        shots_data = divide_into_shots(dialogs)
        shots = []
        for i, shot_lines in enumerate(shots_data):
            shot_id = f"{sc_id}_{i+1:03d}"
            title = shot_lines[0]["text"][:8] + "..." if count_chars(shot_lines[0]["text"]) > 8 else shot_lines[0]["text"]
            chars_in_shot = [{"ref": CHAR_ID.get(l["speaker"]), "action": "对话", "emotion": ""} for l in shot_lines if l["speaker"] in CHAR_ID]
            shots.append({
                "id": shot_id, "title": title, "shot_type": "中景",
                "script_lines": {"start": 0, "end": 0},
                "characters": [c for c in chars_in_shot if c["ref"]],
                "composition": {"angle": "平视", "focus": shot_lines[0]["speaker"] if shot_lines[0]["speaker"] != "旁白" else "场景"},
                "mood": scene_info.get("mood", ""), "lighting": "烛光/自然光",
                "lines": [{"speaker": l["speaker"], "text": l["text"]} for l in shot_lines],
                "prompt": gen_prompt(shot_lines, scene_info, style_base).strip(),
                "image_path": f"{sc_id}_{sc_name}/shot_{i+1:03d}.png",
                "image_status": "pending",
            })
        (SHOTS_DIR / f"{sc_id}_{sc_name}").mkdir(exist_ok=True)
        scene_yaml = {
            "scene_id": sc_id, "scene_name": sc_name, "scene_ref": f"scenes/{path.name}",
            "scene_type": scene_info.get("type", "reality"),
            "scene_description": scene_info.get("location", ""), "scene_mood": scene_info.get("mood", ""),
            "scene_lighting": "宫廷光效", "shots": shots,
        }
        (SHOTS_DIR / f"{sc_id}_{sc_name}.yaml").write_text(
            yaml.dump(scene_yaml, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
        files_info.append({"file": f"{sc_id}_{sc_name}.yaml", "scene_id": sc_id, "scene_name": sc_name, "shots_count": len(shots), "images_ready": 0})
        total_shots += len(shots)
        print(f"  ✓ {path.name} → {len(shots)} 镜头")

    manifest = {"version": "1.0", "script_name": "全班穿成NPC，我把宫斗玩成总动员", "style_base": style_base,
        "source_script": "全班穿成NPC_对话脚本.md", "scene_index": "全班穿成NPC_场景索引.yaml",
        "character_asset": "全班穿成NPC_角色资产.yaml", "generated_at": datetime.now().isoformat(),
        "total_scenes": len(files_info), "total_shots": total_shots, "files": files_info}
    (SHOTS_DIR / "_manifest.yaml").write_text(yaml.dump(manifest, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    print(f"\n✅ 分镜生成完成: {total_shots} 镜头, {len(files_info)} 场景")


if __name__ == "__main__":
    main()
