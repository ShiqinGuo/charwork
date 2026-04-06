import os
import zipfile
import shutil
import tempfile
import logging
import math
from typing import List, Tuple


logger = logging.getLogger(__name__)


def extract_zip_to_temp(zip_path: str, output_dir: str) -> str:
    """
    功能描述：
        提取ziptotemp。

    参数：
        zip_path (str): 文件或资源路径。
        output_dir (str): 字符串结果。

    返回值：
        str: 返回str类型的处理结果。
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    temp_dir = tempfile.mkdtemp(dir=output_dir)
    img_folder = os.path.join(temp_dir, "img")
    os.makedirs(img_folder, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if file.lower().endswith(('.jpg', '.png', '.jpeg')):
                    filename = os.path.basename(file)
                    if filename:
                        source = zip_ref.open(file)
                        target = open(os.path.join(img_folder, filename), "wb")
                        with source, target:
                            shutil.copyfileobj(source, target)
    except Exception as e:
        logger.error(f"解压 ZIP 失败：{zip_path}，错误：{str(e)}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError(f"解压 ZIP 失败：{str(e)}")

    return temp_dir


def merge_images(image_paths: List[str], grid_size: Tuple[int, int] = (10, 10)) -> List[str]:
    """
    功能描述：
        合并图片。

    参数：
        image_paths (List[str]): 待处理图片路径列表。
        grid_size (Tuple[int, int]): Tuple[int, int] 类型的数据。

    返回值：
        List[str]: 返回List[str]类型的处理结果。
    """

    from PIL import Image

    if not image_paths:
        raise ValueError("没有可用于合并的有效图片")

    batch_size = grid_size[0] * grid_size[1]
    batches = [image_paths[i:i + batch_size] for i in range(0, len(image_paths), batch_size)]
    merged_paths = []

    for batch_paths in batches:
        images = [Image.open(p) for p in batch_paths]
        cols, rows = grid_size
        num = len(images)
        actual_cols = min(cols, num)
        actual_rows = math.ceil(num / cols) if num != cols * rows else rows

        w, h = images[0].size
        need_resize = max(w * actual_cols, h * actual_rows) > 2160
        if need_resize:
            scale = min(2160 / (w * actual_cols), 2160 / (h * actual_rows))
            w, h = int(w * scale), int(h * scale)

        merged_img = Image.new('RGB', (w * actual_cols, h * actual_rows), (255, 255, 255))

        for i, img in enumerate(images):
            x = (i % cols) * w
            y = (i // cols) * h
            if need_resize:
                img = img.resize((w, h), Image.Resampling.LANCZOS)
            merged_img.paste(img, (x, y))

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        merged_img.save(tmp.name, quality=95)
        merged_paths.append(tmp.name)

    return merged_paths
