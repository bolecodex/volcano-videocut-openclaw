#!/usr/bin/env python3
"""
分镜 YAML → HTML 可视化剧本生成器

读取 _manifest.yaml 和所有场景分镜 YAML，生成自包含的 HTML 可视化页面。
无需启动 HTTP 服务器，双击即可打开。

用法:
    python generate_storyboard.py --project "{项目目录}/"
    python generate_storyboard.py --project "杀猪匠的使命/" --output "杀猪匠的使命/index.html"
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误: 请先安装 PyYAML → pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ── 默认路径 ──────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_TEMPLATE = SKILL_DIR / "templates" / "storyboard-viewer.html"


# ── 数据加载 ──────────────────────────────────────────────


def load_yaml(path: str) -> dict:
    """加载 YAML 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_manifest(project_dir: str) -> dict:
    """加载分镜索引"""
    manifest_path = os.path.join(project_dir, "shots", "_manifest.yaml")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"找不到分镜索引: {manifest_path}")
    return load_yaml(manifest_path)


def load_all_scenes(project_dir: str, manifest: dict) -> list:
    """加载所有场景分镜文件，返回场景数据列表"""
    scenes = []
    shots_dir = os.path.join(project_dir, "shots")
    files = manifest.get("files", [])

    for file_info in files:
        filename = file_info.get("file", "")
        filepath = os.path.join(shots_dir, filename)
        if not os.path.exists(filepath):
            print(f"  ⚠️  跳过不存在的文件: {filename}")
            continue
        scene_data = load_yaml(filepath)
        if scene_data:
            scenes.append(scene_data)
            print(f"  ✓ {filename} ({len(scene_data.get('shots', []))} 镜头)")

    return scenes


def merge_scene_data(manifest: dict, scenes: list) -> dict:
    """合并所有场景数据为一个完整数据集"""
    all_shots = []
    all_scenes_info = []

    for scene in scenes:
        scene_info = {
            "id": scene.get("scene_id", ""),
            "name": scene.get("scene_name", ""),
            "type": scene.get("scene_type", "reality"),
            "description": scene.get("scene_description", ""),
            "mood": scene.get("scene_mood", ""),
            "lighting": scene.get("scene_lighting", ""),
        }
        all_scenes_info.append(scene_info)

        for shot in scene.get("shots", []):
            shot["scene_ref"] = scene.get("scene_id", "")
            shot["scene_name"] = scene.get("scene_name", "")
            all_shots.append(shot)

    return {
        "manifest": {
            "script_name": manifest.get("script_name", "未命名"),
            "generated_at": str(manifest.get("generated_at", "")),
            "total_scenes": len(all_scenes_info),
            "total_shots": len(all_shots),
            "source_script": manifest.get("source_script", ""),
            "characters": manifest.get("characters", []),
        },
        "scenes": all_scenes_info,
        "shots": all_shots,
    }


# ── HTML 生成 ─────────────────────────────────────────────


def load_template(path: str) -> str:
    """加载 HTML 模板"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render_html(template: str, data: dict) -> str:
    """将数据注入 HTML 模板"""
    data_json = json.dumps(data, ensure_ascii=False, indent=2)

    # 替换模板中的数据占位符
    html = template.replace("{{STORYBOARD_DATA_JSON}}", data_json)
    html = html.replace("{{SCRIPT_NAME}}", data["manifest"]["script_name"])
    html = html.replace("{{TOTAL_SHOTS}}", str(data["manifest"]["total_shots"]))
    html = html.replace("{{TOTAL_SCENES}}", str(data["manifest"]["total_scenes"]))
    html = html.replace("{{GENERATED_AT}}", data["manifest"]["generated_at"])

    return html


# ── 统计信息 ──────────────────────────────────────────────


def print_stats(data: dict):
    """打印统计信息"""
    shots = data["shots"]
    total = len(shots)
    pending = sum(1 for s in shots if s.get("image_status") == "pending")
    completed = total - pending
    total_lines = sum(len(s.get("lines", [])) for s in shots)

    print(f"\n📊 统计:")
    print(f"   场景数: {data['manifest']['total_scenes']}")
    print(f"   镜头数: {total}")
    print(f"   台词数: {total_lines}")
    print(f"   已生图: {completed}/{total}")
    print(f"   待生图: {pending}/{total}")


# ── 主流程 ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="分镜 YAML → HTML 可视化剧本生成器")
    parser.add_argument(
        "--project", "-p",
        required=True,
        help="项目目录路径（包含 shots/ 子目录）",
    )
    parser.add_argument(
        "--template", "-t",
        default=str(DEFAULT_TEMPLATE),
        help=f"HTML 模板路径 (默认: {DEFAULT_TEMPLATE})",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出 HTML 文件路径 (默认: {项目目录}/index.html)",
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project)

    # 1. 加载分镜索引
    print(f"📖 读取分镜索引: {project_dir}/shots/_manifest.yaml")
    manifest = load_manifest(project_dir)

    # 2. 加载所有场景分镜文件
    file_count = len(manifest.get("files", []))
    print(f"📂 加载 {file_count} 个场景分镜文件:")
    scenes = load_all_scenes(project_dir, manifest)

    # 3. 合并数据
    data = merge_scene_data(manifest, scenes)
    print_stats(data)

    # 4. 加载模板
    print(f"\n📄 加载 HTML 模板: {args.template}")
    template = load_template(args.template)

    # 5. 渲染 HTML
    print("🎨 生成 HTML 可视化剧本...")
    html = render_html(template, data)

    # 6. 写入文件
    output_path = args.output or os.path.join(project_dir, "index.html")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ 分镜可视化页面已生成: {output_path}")
    print(f"   打开查看: open \"{output_path}\"")


if __name__ == "__main__":
    main()
