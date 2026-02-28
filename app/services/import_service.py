import os
import json
import logging
import shutil
import pandas as pd

from datetime import datetime
from typing import Dict, Any, Optional
from app.core.config import settings
from app.services.ocr_service import OCRService
from app.utils.image_utils import extract_zip_to_temp


logger = logging.getLogger(__name__)


class ImportService:
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or os.path.join(settings.MEDIA_ROOT, "import_results")
        self.ocr_service = OCRService()

    async def process_import_task(self,
                                  zip_file_path: str,
                                  level_json_path: Optional[str] = None,
                                  comment_json_path: Optional[str] = None,
                                  status_callback=None
                                  ) -> Dict[str, Any]:
        """
        处理导入任务：解压 ZIP、识别图片、与 JSON 匹配、生成 Excel 结果文件。
        """

        async def update_status(progress: int, message: str):
            if status_callback:
                await status_callback(progress, message)
            logger.info(f"导入进度 {progress}%：{message}")

        await update_status(5, "正在准备导入环境…")

        temp_dir = None
        try:
            os.makedirs(self.output_dir, exist_ok=True)

            level_data = {}
            if level_json_path and os.path.exists(level_json_path):
                with open(level_json_path, 'r', encoding='utf-8') as f:
                    level_data = json.load(f)

            comment_data = {}
            if comment_json_path and os.path.exists(comment_json_path):
                with open(comment_json_path, 'r', encoding='utf-8') as f:
                    comment_data = json.load(f)

            await update_status(15, "正在解压 ZIP…")
            temp_base_dir = os.path.join(settings.MEDIA_ROOT, "temp_import")
            temp_dir = extract_zip_to_temp(zip_file_path, temp_base_dir)
            img_folder = os.path.join(temp_dir, "img")

            image_files = sorted(
                [f for f in os.listdir(img_folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            )

            if not image_files:
                raise ValueError("ZIP 中未找到图片文件")

            total_count = len(image_files)
            await update_status(25, f"共找到 {total_count} 张图片，开始识别…")

            results = []
            success_count = 0
            failed_count = 0
            failed_files = []

            for index, image_file in enumerate(image_files):
                current_progress = int(25 + (index / total_count) * 70)
                if index % max(1, total_count // 20) == 0:
                    await update_status(current_progress, f"正在处理 {index+1}/{total_count}…")

                img_path = os.path.join(img_folder, image_file)
                file_name_without_ext = os.path.splitext(image_file)[0]

                try:
                    char = await self.ocr_service.recognize_image(img_path)

                    if not char:
                        failed_count += 1
                        failed_files.append((image_file, "识别失败"))
                        continue

                    result_row = {
                        'character': char,
                        'structure': "未知结构",
                        'variant': "简体",
                        'level': "D",
                        'comment': "无",
                        'image_path': file_name_without_ext,
                        'file_name': file_name_without_ext
                    }

                    if image_file in level_data:
                        result_row['level'] = level_data[image_file]
                    if image_file in comment_data:
                        result_row['comment'] = comment_data[image_file]

                    results.append(result_row)
                    success_count += 1

                except Exception as e:
                    failed_count += 1
                    failed_files.append((image_file, str(e)))

            await update_status(95, "正在生成 Excel 结果文件…")

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            excel_filename = f"hanzi_import_{timestamp}.xlsx"
            excel_path = os.path.join(self.output_dir, excel_filename)

            df = pd.DataFrame(results)
            df.to_excel(excel_path, index=False)

            if failed_files:
                log_filename = f"hanzi_import_{timestamp}_failed.log"
                log_path = os.path.join(self.output_dir, log_filename)
                with open(log_path, 'w', encoding='utf-8') as f:
                    for fname, reason in failed_files:
                        f.write(f"{fname}: {reason}\n")

            await update_status(100, "导入完成")

            return {
                "status": "success",
                "excel_path": excel_path,
                "excel_url": f"/media/import_results/{excel_filename}",
                "total": total_count,
                "success": success_count,
                "failed": failed_count
            }

        except Exception as e:
            await update_status(100, f"导入失败：{str(e)}")
            logger.error(f"导入任务失败：{str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
