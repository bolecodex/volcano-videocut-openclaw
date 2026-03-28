#!/usr/bin/env python3
"""
将本地音频文件转换为 Base64 编码（带 MIME 前缀）。

用法: python audio_base64.py <audio_path> [-o output.txt]
  或: ./audio_base64.py <audio_path>
不指定 -o 时输出到 stdout。
"""
from __future__ import annotations

import argparse
import base64
import os
import sys


def audio_to_base64(audio_path: str) -> str:
    """
    将本地音频文件转换为Base64编码字符串
    
    Args:
        audio_path (str): 音频文件的本地路径（如 mp3/wav/ogg 等）
    
    Returns:
        str: Base64编码后的字符串（带MIME类型前缀，便于直接使用）
    
    Raises:
        FileNotFoundError: 音频文件不存在时抛出
        IOError: 读取文件失败时抛出
    """
    # 1. 定义常见音频格式的MIME类型（便于拼接前缀）
    mime_map = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.flac': 'audio/flac',
        '.m4a': 'audio/mp4',
        '.aac': 'audio/aac'
    }
    
    try:
        # 2. 获取文件后缀，匹配对应的MIME类型
        file_ext = os.path.splitext(audio_path)[1].lower()
        mime_type = mime_map.get(file_ext, 'audio/octet-stream')  # 未知格式用通用类型
        
        # 3. 以二进制模式读取音频文件
        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()
        
        # 4. 编码为Base64字符串（b64encode返回bytes，需转成str）
        base64_bytes = base64.b64encode(audio_bytes)
        base64_str = base64_bytes.decode('utf-8')
        
        # 5. 拼接MIME前缀（可选，但前端/接口使用时更方便）
        base64_with_mime = f"data:{mime_type};base64,{base64_str}"
        
        return base64_with_mime
    
    except FileNotFoundError:
        raise FileNotFoundError(f"音频文件不存在：{audio_path}")
    except OSError as e:
        raise OSError(f"读取音频文件失败：{e}") from e


def main() -> None:
    parser = argparse.ArgumentParser(
        description="将本地音频文件转换为 Base64 编码（带 MIME 前缀）"
    )
    parser.add_argument("audio_path", help="音频文件路径（如 .mp3 / .wav / .ogg 等）")
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="输出文件路径；不指定则输出到 stdout",
    )
    args = parser.parse_args()
    audio_path = os.path.expanduser(args.audio_path)
    if not os.path.isfile(audio_path):
        print(f"❌ 音频文件不存在：{audio_path}", file=sys.stderr)
        sys.exit(1)
    try:
        result = audio_to_base64(audio_path)
    except (FileNotFoundError, OSError) as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    if args.output:
        out_path = os.path.expanduser(args.output)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"✅ 已写入 {out_path}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()

