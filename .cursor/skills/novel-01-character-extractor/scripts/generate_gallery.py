#!/usr/bin/env python3
"""
角色资产 YAML → HTML 画廊生成器

读取角色资产 YAML 文件，使用 HTML 模板生成可视化展示页面。

用法:
    python generate_gallery.py --input {角色资产}.yaml --template gallery.html --output {输出}.html
    python generate_gallery.py --input 杀猪匠的使命/杀猪匠的使命_角色资产.yaml
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 兼容 PyYAML 缺失的场景：尝试导入，失败时给出提示
try:
    import yaml
except ImportError:
    print("错误: 请先安装 PyYAML → pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ── 默认路径 ──────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_TEMPLATE = SKILL_DIR / "assets" / "templates" / "gallery.html"


# ── 角色分组顺序 ──────────────────────────────────────────

TYPE_ORDER = ["主角", "配角", "群演", "特殊"]
TYPE_LABELS = {
    "主角": "主角",
    "配角": "重要配角",
    "群演": "群演角色",
    "特殊": "特殊角色",
}


# ── 核心函数 ──────────────────────────────────────────────


def load_yaml(path: str) -> dict:
    """加载 YAML 角色资产文件"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_template(path: str) -> str:
    """加载 HTML 模板"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def group_characters(characters: list) -> dict:
    """按 type 字段将角色分组，保持顺序"""
    groups: dict[str, list] = {}
    for char in characters:
        ctype = char.get("type", "群演")
        groups.setdefault(ctype, []).append(char)
    # 按预定义顺序排列，未知类型追加到最后
    ordered: dict[str, list] = {}
    for t in TYPE_ORDER:
        if t in groups:
            ordered[t] = groups.pop(t)
    for t, chars in groups.items():
        ordered[t] = chars
    return ordered


def build_gallery_sections(grouped: dict) -> str:
    """生成分组 HTML 片段"""
    sections = []
    for ctype, chars in grouped.items():
        label = TYPE_LABELS.get(ctype, ctype)
        cards_html = "\n".join(_build_card(c) for c in chars)
        section = f"""<section class="section">
    <div class="section-header">
        <h2 class="section-title">{label}</h2>
        <span class="section-count">{len(chars)}位</span>
    </div>
    <div class="grid">
        {cards_html}
    </div>
</section>"""
        sections.append(section)
    return "\n\n".join(sections)


def _build_card(char: dict) -> str:
    """生成单个角色卡片 HTML"""
    char_id = char.get("id", "").lstrip("@")
    name = char.get("name", "未知")
    image = char.get("image_url", "")
    desc = char.get("description", "")
    # 截断描述到 60 字
    short_desc = desc[:60] + "…" if len(desc) > 60 else desc

    return f"""        <div class="card" onclick="openLightbox('{char_id}')">
            <div class="card-image">
                <img src="{image}" alt="{name}" loading="lazy">
            </div>
            <div class="card-info">
                <h3 class="card-name">{name}</h3>
                <p class="card-id">@{char_id}</p>
                <p class="card-desc">{short_desc}</p>
            </div>
        </div>"""


def build_character_data_json(characters: list) -> str:
    """生成 JS 可用的角色数据 JSON 对象"""
    data = {}
    for char in characters:
        char_id = char.get("id", "").lstrip("@")
        data[char_id] = {
            "name": char.get("name", ""),
            "id": char.get("id", ""),
            "type": char.get("type", ""),
            "image": char.get("image_url", ""),
            "description": char.get("description", ""),
            "features": char.get("immutable_features", []),
            "prompt": char.get("prompt", ""),
        }
    return json.dumps(data, ensure_ascii=False, indent=4)


def load_style_base(asset_data: dict, input_dir: str) -> str:
    """从 style.yaml 加载全局风格词，回退到 asset_data 自身"""
    # 优先从 style_ref 指定的 style.yaml 读取
    style_ref = asset_data.get("style_ref", "")
    if style_ref:
        style_path = os.path.join(input_dir, style_ref)
        if os.path.exists(style_path):
            style_data = load_yaml(style_path)
            style_base = style_data.get("style_base", "")
            if style_base:
                print(f"🎨 从 {style_ref} 读取全局风格词")
                return style_base.strip()
    # 回退：直接从角色资产文件读取（兼容旧格式）
    return asset_data.get("style_base", "")


def render_html(template: str, asset_data: dict, input_dir: str = ".") -> str:
    """将模板中的占位符替换为实际数据"""
    characters = asset_data.get("characters", [])
    grouped = group_characters(characters)

    project_name = asset_data.get("project_name", "未命名项目")
    total_count = len(characters)
    main_count = len(grouped.get("主角", [])) + len(grouped.get("配角", []))
    style_base = load_style_base(asset_data, input_dir)
    generated_time = asset_data.get("generated_at", datetime.now().strftime("%Y-%m-%d"))
    # 只取日期部分
    if "T" in str(generated_time):
        generated_time = str(generated_time).split("T")[0]

    gallery_sections = build_gallery_sections(grouped)
    character_json = build_character_data_json(characters)

    html = template
    html = html.replace("{{PROJECT_NAME}}", project_name)
    html = html.replace("{{TOTAL_COUNT}}", str(total_count))
    html = html.replace("{{MAIN_COUNT}}", str(main_count))
    html = html.replace("{{STYLE_BASE}}", style_base)
    html = html.replace("{{GALLERY_SECTIONS}}", gallery_sections)
    html = html.replace("{{CHARACTER_DATA_JSON}}", character_json)
    html = html.replace("{{GENERATED_TIME}}", str(generated_time))

    return html


# ── 主流程 ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="角色资产 YAML → HTML 画廊生成器")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="角色资产 YAML 文件路径",
    )
    parser.add_argument(
        "--template", "-t",
        default=str(DEFAULT_TEMPLATE),
        help=f"HTML 模板路径 (默认: {DEFAULT_TEMPLATE})",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出 HTML 文件路径 (默认: 与 YAML 同目录下的 {项目名}_角色展示.html)",
    )
    args = parser.parse_args()

    # 1. 加载数据
    print(f"📖 读取角色资产: {args.input}")
    asset_data = load_yaml(args.input)

    # 2. 加载模板
    print(f"📄 加载 HTML 模板: {args.template}")
    template = load_template(args.template)

    # 3. 确定输出路径
    input_dir = os.path.dirname(os.path.abspath(args.input))
    if args.output:
        output_path = args.output
    else:
        project_name = asset_data.get("project_name", "未命名项目")
        output_path = os.path.join(input_dir, f"{project_name}_角色展示.html")

    # 4. 渲染 HTML
    print("🎨 生成 HTML 画廊...")
    html = render_html(template, asset_data, input_dir)

    # 5. 写入文件
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 角色展示页面已生成: {output_path}")
    print(f"   角色总数: {len(asset_data.get('characters', []))}")
    print(f"   打开查看: open \"{output_path}\"")


if __name__ == "__main__":
    main()
