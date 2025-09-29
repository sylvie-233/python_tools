"""
转换音频格式

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

def convert_audio(src: str, output_ext: str="mp3", codec: str="aac"):
    """
    使用 ffmpeg 转换音频格式
    :param src: 源文件路径
    :param output_ext: 输出格式扩展名（不带点，如 "mp3"、"wav"）
    :param codec: 音频编码方式 ("aac", "mp3", "copy" 等)
    """
    if not os.path.isfile(src):
        raise FileNotFoundError(f"文件不存在: {src}")

    dst = os.path.splitext(src)[0] + f".{output_ext}"
    dst = get_non_conflicting_path(dst)

    command = ["ffmpeg", "-i", src]

    if codec == "copy":
        command += ["-c:a", "copy"]  # 不转码，直接封装
    else:
        command += ["-c:a", codec]   # 转码为指定音频编码

    command += [dst, "-y"]

    print(f"正在转换: {src} -> {dst}")
    subprocess.run(command, check=True)
    print("转换完成 ✅")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="音频格式转换脚本（支持自定义输入/输出格式）")
    parser.add_argument("src", help="输入文件或目录")
    parser.add_argument("--input-ext", default="wav", help="输入文件扩展名（默认 wav）")
    parser.add_argument("--output-ext", default="mp3", help="输出文件扩展名（默认 mp3）")
    parser.add_argument("--codec", default="aac", help="音频编码方式（默认 aac，可用 copy 保持原始编码）")
    args = parser.parse_args()

    input_ext = args.input_ext.lower().lstrip(".")
    output_ext = args.output_ext.lower().lstrip(".")

    if os.path.isdir(args.src):
        for file in os.listdir(args.src):
            if file.lower().endswith(f".{input_ext}"):
                audio_path = os.path.join(args.src, file)
                convert_audio(audio_path, output_ext, args.codec)
    else:
        convert_audio(args.src, output_ext, args.codec)
