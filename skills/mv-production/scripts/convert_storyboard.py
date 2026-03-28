import json

with open('/Users/bytedance/Desktop/work/skill/music_output/Old_MacDonald/storyboard.json', 'r') as f:
    data = json.load(f)

shots = data.get('shots', [])

with open('/Users/bytedance/Desktop/work/skill/music_output/Old_MacDonald/storyboard.json', 'w') as f:
    json.dump(shots, f, indent=2)

print(f'已转换，共 {len(shots)} 个镜头')
