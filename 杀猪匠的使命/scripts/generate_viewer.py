#!/usr/bin/env python3
"""从 shots/*.yaml 读取分镜数据，生成 HTML 查看器"""

import yaml
import os
import html
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
SHOTS_DIR = BASE_DIR / "shots"
OUTPUT_HTML = BASE_DIR / "shots-viewer.html"

# 按文件名排序读取所有场景 YAML
SCENE_FILES = sorted(SHOTS_DIR.glob("SC_*.yaml"))


def load_scene(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def escape(text):
    return html.escape(str(text)) if text else ""


def build_shot_card(shot, global_idx, shot_num):
    """生成单个镜头卡片的 HTML"""
    title = escape(shot.get("title", ""))
    shot_type = escape(shot.get("shot_type", ""))
    image_url = shot.get("image_url", "")
    mood = escape(shot.get("mood", ""))
    lighting = escape(shot.get("lighting", ""))

    # 角色信息
    characters = shot.get("characters", [])
    char_parts = []
    for c in characters:
        if isinstance(c, dict):
            ref = c.get("ref", "")
            action = c.get("action", "")
            emotion = c.get("emotion", "")
            parts = [ref]
            if action:
                parts.append(f"· {action}")
            if emotion:
                parts.append(f"· {emotion}")
            char_parts.append(" ".join(parts))
        elif isinstance(c, str):
            char_parts.append(c)
    char_text = escape(" | ".join(char_parts)) if char_parts else ""

    # 台词
    lines_html = ""
    lines = shot.get("lines", [])
    if lines:
        items = []
        for line in lines:
            speaker = escape(line.get("speaker", ""))
            text = escape(line.get("text", ""))
            items.append(
                f'<div class="line-item">'
                f'<span class="line-speaker">{speaker}：</span>'
                f'<span class="line-text">{text}</span>'
                f"</div>"
            )
        lines_html = f'<div class="lines-section">{"".join(items)}</div>'

    return f"""<div class="shot-card" onclick="openLightbox({global_idx})">
    <div class="shot-image-container">
        <img class="shot-image" src="{escape(image_url)}" alt="{title}" loading="lazy"
             onerror="this.onerror=null;this.parentElement.classList.add('img-error');">
        <span class="shot-number">{shot_num:02d}</span>
        <span class="shot-type-badge">{shot_type}</span>
    </div>
    <div class="shot-info">
        <h3 class="shot-title">{title}</h3>
        {f'<div class="shot-characters">{char_text}</div>' if char_text else ''}
        <div class="shot-mood">
            {f'<span class="tag tag-mood">🎭 {mood}</span>' if mood else ''}
            {f'<span class="tag tag-lighting">💡 {lighting}</span>' if lighting else ''}
        </div>
        {lines_html}
    </div>
</div>"""


def build_scene_section(scene_data, start_idx):
    """生成单个场景区块的 HTML"""
    scene_id = scene_data.get("scene_id", "")
    scene_name = escape(scene_data.get("scene_name", ""))
    scene_type = escape(scene_data.get("scene_type", ""))
    scene_mood = escape(scene_data.get("scene_mood", ""))
    scene_lighting = escape(scene_data.get("scene_lighting", ""))

    shots = scene_data.get("shots", [])
    cards = []
    for i, shot in enumerate(shots):
        cards.append(build_shot_card(shot, start_idx + i, i + 1))

    return (
        f"""
<!-- {scene_id} {scene_name} -->
<div class="scene-section" id="{scene_id}">
    <div class="scene-header">
        <span class="scene-id">{scene_id}</span>
        <h2 class="scene-title">{scene_name}</h2>
        <div class="scene-meta">
            <span>🎬 {scene_type}</span>
            <span>🎭 {scene_mood}</span>
            <span>💡 {scene_lighting}</span>
        </div>
    </div>
    <div class="shots-grid">
        {"".join(cards)}
    </div>
</div>""",
        len(shots),
    )


def main():
    scenes = []
    all_shots_js = []
    total_shots = 0
    total_images = 0

    for filepath in SCENE_FILES:
        scene = load_scene(filepath)
        scenes.append(scene)

    # 构建 JS 数据和 HTML 区块
    scene_sections = []
    scene_nav_buttons = []
    global_idx = 0

    for scene in scenes:
        sid = scene.get("scene_id", "")
        sname = escape(scene.get("scene_name", ""))
        shots = scene.get("shots", [])

        # 导航按钮
        scene_nav_buttons.append(
            f'<button class="scene-nav-btn" onclick="scrollToScene(\'{sid}\')">{sid} {sname}</button>'
        )

        # 场景区块
        section_html, count = build_scene_section(scene, global_idx)
        scene_sections.append(section_html)

        # JS 数据
        for shot in shots:
            title = shot.get("id", "") + " " + shot.get("title", "")
            desc = (shot.get("shot_type", "") + " · " + shot.get("mood", ""))
            url = shot.get("image_url", "")
            total_shots += 1
            if url:
                total_images += 1
            all_shots_js.append(
                f'{{ url: "{url}", title: "{escape(title)}", desc: "{escape(desc)}" }}'
            )
            global_idx += 1

    # 构建完整 HTML
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>杀猪匠的使命 - 分镜查看器</title>
    <style>
        :root {{
            --bg-primary: #0f0f0f;
            --bg-secondary: #1a1a1a;
            --bg-card: #242424;
            --text-primary: #f0f0f0;
            --text-secondary: #a0a0a0;
            --accent: #d4a853;
            --accent-dim: #8b7355;
            --border: #333;
            --success: #4ade80;
            --shadow: rgba(0,0,0,0.4);
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        /* 页面标题 */
        .page-header {{
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem;
            background: linear-gradient(135deg, #2a2520 0%, var(--bg-card) 100%);
            border-radius: 16px;
            border: 1px solid var(--border);
        }}
        
        .page-title {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--accent);
            margin-bottom: 0.5rem;
        }}
        
        .page-subtitle {{
            color: var(--text-secondary);
            font-size: 1.1rem;
        }}
        
        .stats {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1.5rem;
            flex-wrap: wrap;
        }}
        
        .stat-item {{ text-align: center; }}
        .stat-value {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
        .stat-label {{ font-size: 0.85rem; color: var(--text-secondary); }}
        
        /* 场景导航 */
        .scene-nav {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 2rem;
            justify-content: center;
            position: sticky;
            top: 0;
            z-index: 100;
            background: var(--bg-primary);
            padding: 1rem 0;
            border-bottom: 1px solid var(--border);
        }}
        
        .scene-nav-btn {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.9rem;
        }}
        
        .scene-nav-btn:hover, .scene-nav-btn.active {{
            background: var(--accent);
            color: var(--bg-primary);
            border-color: var(--accent);
        }}
        
        /* 场景区块 */
        .scene-section {{ margin-bottom: 3rem; }}
        
        .scene-header {{
            background: linear-gradient(135deg, #2a2520 0%, var(--bg-card) 100%);
            border-radius: 16px;
            padding: 1.5rem 2rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 1rem;
            flex-wrap: wrap;
        }}
        
        .scene-title {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
        
        .scene-id {{
            font-size: 0.85rem;
            background: var(--accent-dim);
            color: var(--bg-primary);
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-weight: 600;
        }}
        
        .scene-meta {{
            margin-left: auto;
            display: flex;
            gap: 1.5rem;
            font-size: 0.9rem;
            color: var(--text-secondary);
            flex-wrap: wrap;
        }}
        
        /* 镜头网格 */
        .shots-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 1.5rem;
        }}
        
        @media (max-width: 500px) {{
            .shots-grid {{ grid-template-columns: 1fr; }}
        }}
        
        .shot-card {{
            background: var(--bg-card);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            cursor: pointer;
        }}
        
        .shot-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 32px var(--shadow);
        }}
        
        .shot-image-container {{
            position: relative;
            aspect-ratio: 16/9;
            background: var(--bg-secondary);
            overflow: hidden;
        }}
        
        .shot-image {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: opacity 0.3s;
        }}
        
        .shot-image-container.img-error .shot-image {{
            opacity: 0;
        }}
        
        .shot-image-container.img-error::after {{
            content: '🎬 图片加载失败';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        .shot-number {{
            position: absolute;
            top: 0.75rem;
            left: 0.75rem;
            background: var(--accent);
            color: var(--bg-primary);
            width: 32px;
            height: 32px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.85rem;
            z-index: 2;
        }}
        
        .shot-type-badge {{
            position: absolute;
            top: 0.75rem;
            right: 0.75rem;
            background: rgba(0,0,0,0.7);
            color: var(--text-primary);
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            z-index: 2;
        }}
        
        .shot-info {{ padding: 1rem; }}
        
        .shot-title {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: var(--text-primary);
        }}
        
        .shot-characters {{
            font-size: 0.85rem;
            color: var(--accent-dim);
            margin-bottom: 0.5rem;
        }}
        
        .shot-mood {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}
        
        .tag {{
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
        }}
        
        .tag-mood {{
            background: rgba(212, 168, 83, 0.2);
            color: var(--accent);
        }}
        
        .tag-lighting {{
            background: rgba(139, 115, 85, 0.3);
            color: #c4a87a;
        }}
        
        /* 台词区域 */
        .lines-section {{
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid var(--border);
        }}
        
        .line-item {{
            font-size: 0.85rem;
            margin-bottom: 0.5rem;
            padding-left: 0.5rem;
            border-left: 2px solid var(--accent-dim);
        }}
        
        .line-speaker {{ color: var(--accent); font-weight: 600; }}
        .line-text {{ color: var(--text-secondary); }}
        
        /* 灯箱 */
        .lightbox {{
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 2rem;
        }}
        
        .lightbox.active {{ display: flex; }}
        
        .lightbox-content {{
            max-width: 90vw;
            max-height: 90vh;
            position: relative;
        }}
        
        .lightbox-image {{
            max-width: 100%;
            max-height: 80vh;
            border-radius: 8px;
        }}
        
        .lightbox-info {{
            background: var(--bg-card);
            padding: 1rem;
            border-radius: 0 0 8px 8px;
            margin-top: -4px;
        }}
        
        .lightbox-title {{
            font-size: 1.2rem;
            color: var(--accent);
            margin-bottom: 0.5rem;
        }}
        
        .lightbox-close {{
            position: absolute;
            top: -40px;
            right: 0;
            background: none;
            border: none;
            color: var(--text-primary);
            font-size: 2rem;
            cursor: pointer;
            padding: 0.5rem;
        }}
        
        .lightbox-nav {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: var(--bg-card);
            border: none;
            color: var(--text-primary);
            font-size: 1.5rem;
            cursor: pointer;
            padding: 1rem;
            border-radius: 8px;
            opacity: 0.8;
            transition: opacity 0.2s;
        }}
        
        .lightbox-nav:hover {{ opacity: 1; }}
        .lightbox-prev {{ left: -60px; }}
        .lightbox-next {{ right: -60px; }}
        
        @media (max-width: 768px) {{
            .lightbox-prev {{ left: 10px; }}
            .lightbox-next {{ right: 10px; }}
        }}
        
        /* 返回顶部 */
        .back-to-top {{
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: var(--accent);
            color: var(--bg-primary);
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 16px var(--shadow);
            transition: all 0.2s;
            z-index: 50;
        }}
        
        .back-to-top.visible {{ display: flex; }}
        .back-to-top:hover {{ transform: scale(1.1); }}
        
        /* 镜头计数 */
        .shot-counter {{
            position: absolute;
            bottom: 0.75rem;
            left: 0.75rem;
            background: rgba(0,0,0,0.7);
            color: var(--text-secondary);
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-size: 0.7rem;
            z-index: 2;
        }}
        
        /* 滚动条 */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg-secondary); }}
        ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--accent-dim); }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 页面标题 -->
        <div class="page-header">
            <h1 class="page-title">🎬 杀猪匠的使命</h1>
            <p class="page-subtitle">分镜查看器 · Storyboard Viewer</p>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-value" id="stat-scenes">{len(scenes)}</div>
                    <div class="stat-label">场景</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="stat-shots">{total_shots}</div>
                    <div class="stat-label">镜头</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="stat-images">{total_images}</div>
                    <div class="stat-label">图片</div>
                </div>
            </div>
            <p class="page-subtitle" style="margin-top:1rem;font-size:0.85rem;opacity:0.6;">生成时间: {now}</p>
        </div>
        
        <!-- 场景导航 -->
        <div class="scene-nav">
            <button class="scene-nav-btn active" onclick="scrollToScene('all')">全部</button>
            {"".join(scene_nav_buttons)}
        </div>
        
        {"".join(scene_sections)}
    </div>
    
    <!-- 灯箱 -->
    <div class="lightbox" id="lightbox">
        <div class="lightbox-content">
            <button class="lightbox-close" onclick="closeLightbox()">&times;</button>
            <button class="lightbox-nav lightbox-prev" onclick="prevImage()">&#8249;</button>
            <button class="lightbox-nav lightbox-next" onclick="nextImage()">&#8250;</button>
            <img class="lightbox-image" id="lightbox-image" src="" alt="">
            <div class="lightbox-info">
                <h3 class="lightbox-title" id="lightbox-title"></h3>
                <p id="lightbox-desc" style="color: var(--text-secondary); font-size: 0.9rem;"></p>
                <p id="lightbox-counter" style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.5rem;"></p>
            </div>
        </div>
    </div>
    
    <!-- 返回顶部 -->
    <button class="back-to-top" id="backToTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">↑</button>
    
    <script>
        const allShots = [
            {",".join(all_shots_js)}
        ];
        
        let currentIndex = 0;
        
        function openLightbox(index) {{
            currentIndex = index;
            updateLightbox();
            document.getElementById('lightbox').classList.add('active');
            document.body.style.overflow = 'hidden';
        }}
        
        function closeLightbox() {{
            document.getElementById('lightbox').classList.remove('active');
            document.body.style.overflow = '';
        }}
        
        function updateLightbox() {{
            const shot = allShots[currentIndex];
            document.getElementById('lightbox-image').src = shot.url;
            document.getElementById('lightbox-title').textContent = shot.title;
            document.getElementById('lightbox-desc').textContent = shot.desc;
            document.getElementById('lightbox-counter').textContent = `${{currentIndex + 1}} / ${{allShots.length}}`;
        }}
        
        function prevImage() {{
            currentIndex = (currentIndex - 1 + allShots.length) % allShots.length;
            updateLightbox();
        }}
        
        function nextImage() {{
            currentIndex = (currentIndex + 1) % allShots.length;
            updateLightbox();
        }}
        
        function scrollToScene(sceneId) {{
            document.querySelectorAll('.scene-nav-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            if (sceneId === 'all') {{
                window.scrollTo({{ top: 0, behavior: 'smooth' }});
            }} else {{
                document.getElementById(sceneId).scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
        }}
        
        // 键盘导航
        document.addEventListener('keydown', (e) => {{
            if (!document.getElementById('lightbox').classList.contains('active')) return;
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') prevImage();
            if (e.key === 'ArrowRight') nextImage();
        }});
        
        // 点击背景关闭灯箱
        document.getElementById('lightbox').addEventListener('click', (e) => {{
            if (e.target.id === 'lightbox') closeLightbox();
        }});
        
        // 返回顶部按钮
        window.addEventListener('scroll', () => {{
            const btn = document.getElementById('backToTop');
            btn.classList.toggle('visible', window.scrollY > 500);
        }});
    </script>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"✅ 查看器已生成: {OUTPUT_HTML}")
    print(f"   场景: {len(scenes)}")
    print(f"   镜头: {total_shots}")
    print(f"   图片: {total_images}")


if __name__ == "__main__":
    main()
