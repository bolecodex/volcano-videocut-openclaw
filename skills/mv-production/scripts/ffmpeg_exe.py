"""
提供 ffmpeg 可执行路径：仅使用 imageio-ffmpeg 包内嵌的 ffmpeg，不依赖用户本机安装。
"""
def get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError(
            "未找到 imageio-ffmpeg，所有 ffmpeg 调用均使用该包。请安装: pip install imageio-ffmpeg"
        ) from e
