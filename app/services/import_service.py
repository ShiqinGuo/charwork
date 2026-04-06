"""
为什么这样做：导入流程拆为“准备-识别-产物生成”阶段并显式上报进度，便于长任务可观测与故障定位。
特殊逻辑：默认元数据与失败日志均配置化，保证缺少外部映射或部分识别失败时仍能产出可追溯结果。
"""

import logging
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

import pandas as pd

from app.core.config import settings
from app.services.ocr_service import OCRService
from app.utils.image_utils import extract_zip_to_temp


logger = logging.getLogger(__name__)


IMPORT_RESULTS_DIR_NAME = "import_results"
TEMP_IMPORT_DIR_NAME = "temp_import"
IMAGE_DIR_NAME = "img"
OUTPUT_FILE_PREFIX = "hanzi_import"
FAILED_LOG_FILE_SUFFIX = "_failed.log"
EXCEL_FILE_EXTENSION = ".xlsx"
SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
DEFAULT_STRUCTURE = "未知结构"
DEFAULT_VARIANT = "简体"
DEFAULT_LEVEL = "D"
DEFAULT_COMMENT = "无"
SUCCESS_STATUS = "success"
ERROR_STATUS = "error"
PREPARE_PROGRESS = 5
EXTRACT_PROGRESS = 15
RECOGNIZE_START_PROGRESS = 25
RESULT_FILE_PROGRESS = 95
COMPLETE_PROGRESS = 100
RECOGNIZE_PROGRESS_RANGE = RESULT_FILE_PROGRESS - RECOGNIZE_START_PROGRESS
PROGRESS_REPORT_STEPS = 20
OUTPUT_URL_PREFIX = f"/media/{IMPORT_RESULTS_DIR_NAME}"
PREPARE_STATUS_MESSAGE = "正在准备导入环境…"
EXTRACT_STATUS_MESSAGE = "正在解压 ZIP…"
RESULT_FILE_STATUS_MESSAGE = "正在生成 Excel 结果文件…"
COMPLETE_STATUS_MESSAGE = "导入完成"
FAILED_RECOGNITION_REASON = "识别失败"
DEFAULT_RESULT_ROW = {
    "structure": DEFAULT_STRUCTURE,
    "variant": DEFAULT_VARIANT,
    "level": DEFAULT_LEVEL,
    "comment": DEFAULT_COMMENT,
}

StatusCallback = Callable[[int, str], Awaitable[None]]
MetadataMapping = dict[str, Any]
ResultRow = dict[str, Any]
ServiceResult = dict[str, Any]
FailedFileEntry = tuple[str, str]


@dataclass(frozen=True)
class ImportContext:
    temp_dir: str
    image_dir: str
    image_files: list[str]
    level_data: MetadataMapping
    comment_data: MetadataMapping


@dataclass(frozen=True)
class RecognitionSummary:
    results: list[ResultRow]
    success_count: int
    failed_count: int
    failed_files: list[FailedFileEntry]


@dataclass(frozen=True)
class GeneratedFiles:
    excel_path: str
    excel_url: str


class ImportService:
    def __init__(self, output_dir: Optional[str] = None):
        """
        功能描述：
            初始化ImportService并准备运行所需的依赖对象。

        参数：
            output_dir (Optional[str]): 字符串结果。

        返回值：
            None: 无返回值。
        """
        self.output_dir = output_dir or os.path.join(settings.MEDIA_ROOT, IMPORT_RESULTS_DIR_NAME)
        self.ocr_service = OCRService()

    async def process_import_task(
        self,
        zip_file_path: str,
        level_json_path: Optional[str] = None,
        comment_json_path: Optional[str] = None,
        status_callback: Optional[StatusCallback] = None,
    ) -> ServiceResult:
        """
        功能描述：
            处理导入任务。

        参数：
            zip_file_path (str): 文件或资源路径。
            level_json_path (Optional[str]): 文件或资源路径。
            comment_json_path (Optional[str]): 文件或资源路径。
            status_callback (Optional[StatusCallback]): 状态信息。

        返回值：
            ServiceResult: 返回ServiceResult类型的处理结果。
        """
        update_status = self._build_status_updater(status_callback)
        await update_status(PREPARE_PROGRESS, PREPARE_STATUS_MESSAGE)

        temp_dir: Optional[str] = None
        try:
            self._ensure_output_dir()
            # 先统一准备临时目录、图片列表与补充元数据，后续识别阶段只消费标准化上下文。
            context = await self._prepare_import_context(
                zip_file_path=zip_file_path,
                level_json_path=level_json_path,
                comment_json_path=comment_json_path,
                update_status=update_status,
            )
            temp_dir = context.temp_dir
            total_count = len(context.image_files)

            await update_status(RECOGNIZE_START_PROGRESS, f"共找到 {total_count} 张图片，开始识别…")
            summary = await self._recognize_images(context, update_status)

            await update_status(RESULT_FILE_PROGRESS, RESULT_FILE_STATUS_MESSAGE)
            # 结果文件在识别完成后统一生成，避免中途中断时留下不完整的导出产物。
            generated_files = self._generate_result_files(summary.results, summary.failed_files)

            await update_status(COMPLETE_PROGRESS, COMPLETE_STATUS_MESSAGE)
            return self._build_success_response(
                generated_files=generated_files,
                total_count=total_count,
                summary=summary,
            )
        except Exception as exc:
            await update_status(COMPLETE_PROGRESS, f"导入失败：{exc}")
            logger.error(f"导入任务失败：{exc}", exc_info=True)
            return self._build_error_response(str(exc))
        finally:
            self._cleanup_temp_dir(temp_dir)

    def _build_status_updater(
        self,
        status_callback: Optional[StatusCallback],
    ) -> StatusCallback:
        """
        功能描述：
            构建状态updater。

        参数：
            status_callback (Optional[StatusCallback]): 状态信息。

        返回值：
            StatusCallback: 返回StatusCallback类型的处理结果。
        """
        async def update_status(progress: int, message: str) -> None:
            """
            功能描述：
                更新状态并返回最新结果。

            参数：
                progress (int): 整数结果。
                message (str): 字符串结果。

            返回值：
                None: 无返回值。
            """
            if status_callback:
                await status_callback(progress, message)
            logger.info(f"导入进度 {progress}%：{message}")

        return update_status

    def _ensure_output_dir(self) -> None:
        """
        功能描述：
            确保outputdir存在，必要时自动补齐。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        os.makedirs(self.output_dir, exist_ok=True)

    async def _prepare_import_context(
        self,
        zip_file_path: str,
        level_json_path: Optional[str],
        comment_json_path: Optional[str],
        update_status: StatusCallback,
    ) -> ImportContext:
        """
        功能描述：
            处理导入context。

        参数：
            zip_file_path (str): 文件或资源路径。
            level_json_path (Optional[str]): 文件或资源路径。
            comment_json_path (Optional[str]): 文件或资源路径。
            update_status (StatusCallback): 状态信息。

        返回值：
            ImportContext: 返回ImportContext类型的处理结果。
        """
        level_data, comment_data = self._load_metadata_mappings(level_json_path, comment_json_path)
        await update_status(EXTRACT_PROGRESS, EXTRACT_STATUS_MESSAGE)
        temp_base_dir = os.path.join(settings.MEDIA_ROOT, TEMP_IMPORT_DIR_NAME)
        # ZIP 会先完整解压到临时目录，后续识别、失败回滚与最终清理都围绕同一批临时文件展开。
        temp_dir = extract_zip_to_temp(zip_file_path, temp_base_dir)
        image_dir = os.path.join(temp_dir, IMAGE_DIR_NAME)
        image_files = self._collect_image_files(image_dir)

        return ImportContext(
            temp_dir=temp_dir,
            image_dir=image_dir,
            image_files=image_files,
            level_data=level_data,
            comment_data=comment_data,
        )

    def _load_metadata_mappings(
        self,
        level_json_path: Optional[str],
        comment_json_path: Optional[str],
    ) -> tuple[MetadataMapping, MetadataMapping]:
        """
        功能描述：
            加载metadatamappings。

        参数：
            level_json_path (Optional[str]): 文件或资源路径。
            comment_json_path (Optional[str]): 文件或资源路径。

        返回值：
            tuple[MetadataMapping, MetadataMapping]: 返回tuple[MetadataMapping, MetadataMapping]类型的处理结果。
        """
        return (
            self._load_json_data(level_json_path),
            self._load_json_data(comment_json_path),
        )

    def _load_json_data(self, json_path: Optional[str]) -> MetadataMapping:
        """
        功能描述：
            加载json数据。

        参数：
            json_path (Optional[str]): 文件或资源路径。

        返回值：
            MetadataMapping: 返回MetadataMapping类型的处理结果。
        """
        if not json_path or not os.path.exists(json_path):
            return {}

        with open(json_path, "r", encoding="utf-8") as file:
            loaded_data = json.load(file)
        return loaded_data if isinstance(loaded_data, dict) else {}

    def _collect_image_files(self, image_dir: str) -> list[str]:
        """
        功能描述：
            处理图片文件。

        参数：
            image_dir (str): 字符串结果。

        返回值：
            list[str]: 返回列表形式的结果数据。
        """
        image_files = sorted(
            file_name
            for file_name in os.listdir(image_dir)
            if file_name.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)
        )
        if not image_files:
            raise ValueError("ZIP 中未找到图片文件")
        return image_files

    async def _recognize_images(
        self,
        context: ImportContext,
        update_status: StatusCallback,
    ) -> RecognitionSummary:
        """
        功能描述：
            识别图片。

        参数：
            context (ImportContext): ImportContext 类型的数据。
            update_status (StatusCallback): 状态信息。

        返回值：
            RecognitionSummary: 返回RecognitionSummary类型的处理结果。
        """
        results: list[ResultRow] = []
        failed_files: list[FailedFileEntry] = []
        success_count = 0
        failed_count = 0
        total_count = len(context.image_files)

        for index, image_file in enumerate(context.image_files):
            if self._should_report_progress(index, total_count):
                current_progress = self._calculate_progress(index, total_count)
                await update_status(current_progress, f"正在处理 {index + 1}/{total_count}…")

            try:
                # 单张识别失败不能阻断整批导入，这里按“逐张容错、集中汇总失败原因”的方式处理。
                result_row = await self._recognize_single_image(
                    image_dir=context.image_dir,
                    image_file=image_file,
                    level_data=context.level_data,
                    comment_data=context.comment_data,
                )
                if result_row is None:
                    # OCR 没有返回有效字符时按失败文件记录，便于最终结果中提示人工复核。
                    failed_count, failed_files = self._record_failed_file(
                        failed_count=failed_count,
                        failed_files=failed_files,
                        image_file=image_file,
                        reason=FAILED_RECOGNITION_REASON,
                    )
                    continue

                results.append(result_row)
                success_count += 1
            except Exception as exc:
                failed_count, failed_files = self._record_failed_file(
                    failed_count=failed_count,
                    failed_files=failed_files,
                    image_file=image_file,
                    reason=str(exc),
                )

        return RecognitionSummary(
            results=results,
            success_count=success_count,
            failed_count=failed_count,
            failed_files=failed_files,
        )

    def _should_report_progress(self, index: int, total_count: int) -> bool:
        """
        功能描述：
            处理reportprogress。

        参数：
            index (int): 整数结果。
            total_count (int): 数量值。

        返回值：
            bool: 返回操作是否成功。
        """
        report_interval = max(1, total_count // PROGRESS_REPORT_STEPS)
        return index % report_interval == 0

    def _calculate_progress(self, index: int, total_count: int) -> int:
        """
        功能描述：
            处理progress。

        参数：
            index (int): 整数结果。
            total_count (int): 数量值。

        返回值：
            int: 返回int类型的处理结果。
        """
        return int(RECOGNIZE_START_PROGRESS + (index / total_count) * RECOGNIZE_PROGRESS_RANGE)

    @staticmethod
    def _record_failed_file(
        failed_count: int,
        failed_files: list[FailedFileEntry],
        image_file: str,
        reason: str,
    ) -> tuple[int, list[FailedFileEntry]]:
        """
        功能描述：
            处理failed文件。

        参数：
            failed_count (int): 数量值。
            failed_files (list[FailedFileEntry]): 文件对象或文件标识。
            image_file (str): 文件对象或文件标识。
            reason (str): 字符串结果。

        返回值：
            tuple[int, list[FailedFileEntry]]: 返回tuple[int, list[FailedFileEntry]]类型的处理结果。
        """
        failed_files.append((image_file, reason))
        return failed_count + 1, failed_files

    async def _recognize_single_image(
        self,
        image_dir: str,
        image_file: str,
        level_data: MetadataMapping,
        comment_data: MetadataMapping,
    ) -> Optional[ResultRow]:
        """
        功能描述：
            识别single图片。

        参数：
            image_dir (str): 字符串结果。
            image_file (str): 文件对象或文件标识。
            level_data (MetadataMapping): MetadataMapping 类型的数据。
            comment_data (MetadataMapping): MetadataMapping 类型的数据。

        返回值：
            Optional[ResultRow]: 返回处理结果对象；无可用结果时返回 None。
        """
        image_path = os.path.join(image_dir, image_file)
        file_name_without_ext = os.path.splitext(image_file)[0]
        char = await self.ocr_service.recognize_image(image_path)
        if not char:
            return None

        result_row = self._build_result_row(char, file_name_without_ext)
        self._apply_metadata(result_row, image_file, level_data, comment_data)
        return result_row

    def _build_result_row(self, char: Any, file_name_without_ext: str) -> ResultRow:
        """
        功能描述：
            构建结果row。

        参数：
            char (Any): 字符。
            file_name_without_ext (str): 文件对象或文件标识。

        返回值：
            ResultRow: 返回ResultRow类型的处理结果。
        """
        return {
            **DEFAULT_RESULT_ROW,
            "character": char,
            "image_path": file_name_without_ext,
            "file_name": file_name_without_ext,
        }

    def _apply_metadata(
        self,
        result_row: ResultRow,
        image_file: str,
        level_data: MetadataMapping,
        comment_data: MetadataMapping,
    ) -> None:
        """
        功能描述：
            处理metadata。

        参数：
            result_row (ResultRow): 处理中产生的结果数据。
            image_file (str): 文件对象或文件标识。
            level_data (MetadataMapping): MetadataMapping 类型的数据。
            comment_data (MetadataMapping): MetadataMapping 类型的数据。

        返回值：
            None: 无返回值。
        """
        metadata_sources = (
            ("level", level_data),
            ("comment", comment_data),
        )
        for field_key, metadata_mapping in metadata_sources:
            if image_file not in metadata_mapping:
                continue
            result_row[field_key] = metadata_mapping[image_file]

    def _generate_result_files(
        self,
        results: list[ResultRow],
        failed_files: list[FailedFileEntry],
    ) -> GeneratedFiles:
        """
        功能描述：
            生成结果文件。

        参数：
            results (list[ResultRow]): 处理中产生的结果数据。
            failed_files (list[FailedFileEntry]): 文件对象或文件标识。

        返回值：
            GeneratedFiles: 返回GeneratedFiles类型的处理结果。
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        excel_filename = self._build_output_filename(timestamp, EXCEL_FILE_EXTENSION)
        excel_path = os.path.join(self.output_dir, excel_filename)

        pd.DataFrame(results).to_excel(excel_path, index=False)
        if failed_files:
            self._write_failed_log(timestamp, failed_files)

        return GeneratedFiles(
            excel_path=excel_path,
            excel_url=f"{OUTPUT_URL_PREFIX}/{excel_filename}",
        )

    def _build_output_filename(self, timestamp: str, suffix: str) -> str:
        """
        功能描述：
            构建outputfilename。

        参数：
            timestamp (str): 字符串结果。
            suffix (str): 字符串结果。

        返回值：
            str: 返回str类型的处理结果。
        """
        return f"{OUTPUT_FILE_PREFIX}_{timestamp}{suffix}"

    def _write_failed_log(
        self,
        timestamp: str,
        failed_files: list[FailedFileEntry],
    ) -> None:
        """
        功能描述：
            写入failed日志。

        参数：
            timestamp (str): 字符串结果。
            failed_files (list[FailedFileEntry]): 文件对象或文件标识。

        返回值：
            None: 无返回值。
        """
        log_filename = self._build_output_filename(timestamp, FAILED_LOG_FILE_SUFFIX)
        log_path = os.path.join(self.output_dir, log_filename)
        with open(log_path, "w", encoding="utf-8") as file:
            for file_name, reason in failed_files:
                file.write(f"{file_name}: {reason}\n")

    def _build_success_response(
        self,
        generated_files: GeneratedFiles,
        total_count: int,
        summary: RecognitionSummary,
    ) -> ServiceResult:
        """
        功能描述：
            构建success响应。

        参数：
            generated_files (GeneratedFiles): 文件对象或文件标识。
            total_count (int): 数量值。
            summary (RecognitionSummary): RecognitionSummary 类型的数据。

        返回值：
            ServiceResult: 返回ServiceResult类型的处理结果。
        """
        return {
            "status": SUCCESS_STATUS,
            "excel_path": generated_files.excel_path,
            "excel_url": generated_files.excel_url,
            "total": total_count,
            "success": summary.success_count,
            "failed": summary.failed_count,
        }

    def _build_error_response(self, message: str) -> ServiceResult:
        """
        功能描述：
            构建error响应。

        参数：
            message (str): 字符串结果。

        返回值：
            ServiceResult: 返回ServiceResult类型的处理结果。
        """
        return {
            "status": ERROR_STATUS,
            "message": message,
        }

    def _cleanup_temp_dir(self, temp_dir: Optional[str]) -> None:
        """
        功能描述：
            处理tempdir。

        参数：
            temp_dir (Optional[str]): 字符串结果。

        返回值：
            None: 无返回值。
        """
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
