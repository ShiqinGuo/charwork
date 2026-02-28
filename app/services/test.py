import sys
import os
from pathlib import Path
from dotenv import load_dotenv


def main():
    load_dotenv("D:/mywork/charwork/.env")
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from app.services.ocr_service import OCRService
    service = OCRService()

    base_dir = "D:/mywork/HanziProject/data/提交数据集含答案/Task1/Test/img"
    # 便利文件夹下所有jpg文件
    image_paths = [f"{base_dir}/{file}" for file in os.listdir(base_dir)]

    try:
        import asyncio
        result = asyncio.run(service.batch_recognize(image_paths))
        print("结果:", result)
    except Exception as e:
        print("识别失败:", e)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
