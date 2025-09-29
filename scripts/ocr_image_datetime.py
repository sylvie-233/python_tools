"""
解析图片获取其中的日期，重命名图片文件为日期

pip install easyocr
"""
import os
import re
import argparse
import easyocr
from PIL import Image
import numpy as np

# 初始化 OCR
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)

# 命令行参数（必填）
parser = argparse.ArgumentParser(description="批量 OCR 重命名图片")
parser.add_argument("src", help="源目录，存放待处理图片")
parser.add_argument("dst", help="目标目录，保存重命名后的图片")
args = parser.parse_args()

src_folder = args.src
dst_folder = args.dst

# 确保目标目录存在
os.makedirs(dst_folder, exist_ok=True)

for file in os.listdir(src_folder):
    if not file.lower().endswith((".png", ".jpg", ".jpeg")):
        continue

    src_path = os.path.join(src_folder, file)

    try:
        # 用 PIL 打开图片
        img = Image.open(src_path)
        img_np = np.array(img)

        # OCR
        result = reader.readtext(img_np)
        texts = [text for (_, text, _) in result]

        # 默认使用原文件名
        ans = os.path.splitext(file)[0]

        # 找到含“年”和“日”或“月”的文本
        for item in texts:
            if '年' in item and ('日' in item or '月' in item):
                ans = item.strip()
                break

        # 去掉空格 & 替换 Windows 非法字符
        ans = ans.replace(" ", "")
        ans = re.sub(r'[\\/:*?"<>|]', '_', ans)

        # 提取数字并格式化
        nums = re.findall(r'\d+', ans)
        widths = [4, 2, 2, 2, 2]
        formatted = [num[:widths[i]].zfill(widths[i]) for i, num in enumerate(nums)]
        ans = "_".join(formatted)

        # 构造目标路径
        ext = os.path.splitext(file)[1]
        dst_path = os.path.join(dst_folder, ans + ext)

        # 避免重名
        counter = 1
        while os.path.exists(dst_path):
            dst_path = os.path.join(dst_folder, f"{ans}_{counter}{ext}")
            counter += 1

        # 只在成功完成 OCR + 文件名处理后才移动文件
        try:
            os.rename(src_path, dst_path)
            print(f"{file} -> {os.path.basename(dst_path)}")
        except Exception as e:
            print(f"重命名失败，保留原文件 {file}: {e}")

    except Exception as e:
        print(f"无法解析图片 {file}: {e}")
        # 出现异常时不删除原文件，继续处理下一张
        continue
