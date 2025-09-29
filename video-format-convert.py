"""
转换视频格式

ffmpeg
"""
import os
import subprocess
import argparse

def get_non_conflicting_path(dst: str) -> str:
    """
    如果目标文件已存在，则自动在文件名后加序号，避免覆盖
    """
    base, ext = os.path.splitext(dst)
    counter = 1
    new_dst = dst
    while os.path.exists(new_dst):
        new_dst = f"{base}_{counter}{ext}"
        counter += 1
    return new_dst

def convert_video(src, output_ext="mp4"):
    """
    使用 ffmpeg 转换视频格式
    :param src: 源文件路径
    :param output_ext: 输出格式扩展名（不带点，如 "mp4"、"mkv"）
    """
    if not os.path.isfile(src):
        raise FileNotFoundError(f"文件不存在: {src}")

    dst = os.path.splitext(src)[0] + f".{output_ext}"
    dst = get_non_conflicting_path(dst)

    command = [
        "ffmpeg",
        "-i", src,
        "-c:v", "libx264",  # 视频转码为 H.264（兼容性高）
        "-c:a", "aac",      # 音频转码为 AAC
        "-strict", "experimental",
        dst,
        "-y"
    ]

    print(f"正在转换: {src} -> {dst}")
    subprocess.run(command, check=True)
    print("转换完成 ✅")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="视频格式转换脚本（支持自定义输入/输出格式）")
    parser.add_argument("src", help="输入文件或目录")
    parser.add_argument("--input-ext", default="mov", help="输入文件扩展名（默认 mov）")
    parser.add_argument("--output-ext", default="mp4", help="输出文件扩展名（默认 mp4）")
    args = parser.parse_args()

    input_ext = args.input_ext.lower().lstrip(".")
    output_ext = args.output_ext.lower().lstrip(".")

    if os.path.isdir(args.src):
        for file in os.listdir(args.src):
            if file.lower().endswith(f".{input_ext}"):
                video_path = os.path.join(args.src, file)
                convert_video(video_path, output_ext)
    else:
        convert_video(args.src, output_ext)
