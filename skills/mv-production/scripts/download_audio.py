#!/usr/bin/env python3
"""
通用音频/文件下载脚本。从指定 URL 下载到本地文件，支持流式写入。
"""
import argparse
from pathlib import Path

import requests


def download(url: str, output: Path, chunk_size: int = 8192, timeout: int = 300) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(output, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="从 URL 下载音频或任意文件到本地。")
    parser.add_argument("--url", required=True, help="资源 URL。")
    parser.add_argument("--output", "-o", required=True, help="本地输出路径（含文件名）。")
    parser.add_argument("--chunk-size", type=int, default=8192, help="分块大小（字节），默认 8192。")
    parser.add_argument("--timeout", type=int, default=300, help="请求超时秒数，默认 300。")
    args = parser.parse_args()

    output_path = Path(args.output)
    print(f"Downloading from {args.url} ...")
    download(args.url, output_path, chunk_size=args.chunk_size, timeout=args.timeout)
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
