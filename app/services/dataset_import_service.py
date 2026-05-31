"""
数据集导入服务：并行上传 → 5x5 合并 OCR → pandas 批量处理 → ORM bulk insert。
"""

import json
import logging
import os
import shutil
import uuid as uuid_mod
from concurrent.futures import as_completed, ThreadPoolExecutor
from typing import Any

import pandas as pd
from sqlalchemy import insert, select

from app.core.redis_client import get_sync_redis
from app.models.hanzi import Hanzi
from app.models.hanzi_dictionary import HanziDataset, DatasetHanziRelation, HanziDictionary
from app.services.ocr_service import OCRService
from app.utils.hanzi_dictionary_parser import resolve_pinyin
from app.utils.image_utils import merge_images

logger = logging.getLogger(__name__)

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
REDIS_PROGRESS_PREFIX = "dataset_import:progress:"
REDIS_TTL = 3600
BATCH_SIZE = 1000
GRID_SIZE = (5, 5)
GRID_BATCH = GRID_SIZE[0] * GRID_SIZE[1]

# 上传不限并发，OCR 限流
UPLOAD_THREADS = 20
OCR_THREADS = 1  # 合并后单张识别，不需要多线程


def _safe_int(val) -> int:
    try:
        return int(float(val)) if val is not None and str(val) != "nan" else 0
    except (ValueError, TypeError):
        return 0


def _pub_progress(redis_client, task_id: str, data: dict):
    redis_client.setex(f"{REDIS_PROGRESS_PREFIX}{task_id}", REDIS_TTL, json.dumps(data))


def _calc_progress(stage: str, completed: int, total: int) -> int:
    weights = {"uploading": 40, "recognizing": 90, "saving": 100, "done": 100}
    prevs = {"uploading": 0, "recognizing": 40, "saving": 90, "done": 100}
    base = weights.get(stage, 100) - prevs.get(stage, 0)
    if total > 0 and base > 0:
        return min(weights[stage], prevs.get(stage, 0) + int(base * completed / total))
    return prevs.get(stage, 0)


def _upload_one(path: str, ocr: OCRService) -> dict:
    try:
        if not os.path.isfile(path):
            return {"path": path, "url": "", "status": "failed"}
        info = ocr._upload_image(path)
        img_url = ocr._transform_uri2url(info.get("URI", ""))
        return {"path": path, "url": img_url or "", "status": "ok" if img_url else "failed"}
    except Exception:
        return {"path": path, "url": "", "status": "failed"}


def _ocr_merged(image_paths: list[str], ocr: OCRService) -> list[str]:
    """合并 5x5 → OCR → 返回字符列表（按网格顺序）"""
    merged_paths = merge_images(image_paths, grid_size=GRID_SIZE)
    all_chars: list[str] = []
    for merged_path in merged_paths:
        try:
            result = ocr._upload_image(merged_path)
            merged_url = ocr._transform_uri2url(result.get("URI", ""))
            if not merged_url:
                all_chars.extend([""] * GRID_BATCH)
                continue
            resp = ocr._ai_process_ocr(merged_url)
            text = ocr._extract_text(resp)
            if isinstance(text, str):
                text = list(text) if text else []
            elif not isinstance(text, list):
                text = []
            all_chars.extend(text)
        except Exception:
            all_chars.extend([""] * GRID_BATCH)
        finally:
            try:
                os.unlink(merged_path)
            except OSError:
                pass
    return all_chars


def scan_images(root_dir: str) -> list[str]:
    paths: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root_dir):
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in SUPPORTED_EXTS:
                paths.append(os.path.join(dirpath, fn))
    return paths


def run_dataset_import_sync(
    image_paths: list[str],
    temp_dir: str,
    metadata: dict[str, Any],
    task_id: str,
    db_session_factory,
) -> dict:
    total = len(image_paths)
    redis = get_sync_redis()

    def pub(stage: str, completed: int, message: str):
        _pub_progress(redis, task_id, {
            "progress": _calc_progress(stage, completed, total),
            "stage": stage, "message": message,
            "completed": completed, "total": total,
            "failed_count": 0, "status": "running",
        })

    pub("uploading", 0, f"开始上传 {total} 张图片…")

    # Stage 1: Parallel upload
    ocr = OCRService()
    upload_results: list[dict] = []
    with ThreadPoolExecutor(max_workers=UPLOAD_THREADS) as pool:
        futures = {pool.submit(_upload_one, p, ocr): p for p in image_paths}
        completed = 0
        for f in as_completed(futures):
            upload_results.append(f.result())
            completed += 1
            if completed % max(1, total // 10) == 0 or completed == total:
                pub("uploading", completed, f"上传中 {completed}/{total}")

    pub("uploading", total, "上传完成，开始识别…")

    # Stage 2: Merge 5x5 + OCR
    pub("recognizing", 0, "合并识别中…")
    ok_uploads = [r for r in upload_results if r["status"] == "ok"]
    batches = [ok_uploads[i:i + GRID_BATCH] for i in range(0, len(ok_uploads), GRID_BATCH)]

    all_results: list[dict] = []
    recognized = 0
    for batch in batches:
        batch_paths = [r["path"] for r in batch]
        chars = _ocr_merged(batch_paths, ocr)
        # 映射回原始 url（按网格顺序，左→右 上→下）
        for i, r in enumerate(batch):
            char = chars[i] if i < len(chars) else ""
            all_results.append({"path": r["path"], "url": r["url"], "char": char, "status": "ok"})
        recognized += len(batch)
        pub("recognizing", recognized, f"识别中 {recognized}/{len(ok_uploads)}")

    # 添加失败的
    for r in upload_results:
        if r["status"] != "ok":
            all_results.append({"path": r["path"], "url": "", "char": "", "status": "failed"})

    ok_count = sum(1 for r in all_results if r["char"])
    pub("recognizing", len(ok_uploads), f"识别完成，成功 {ok_count}/{len(ok_uploads)}")

    # Stage 3: Pandas pipeline → bulk insert
    pub("saving", 0, "补充数据并写入数据库…")

    df = pd.DataFrame(all_results)
    ok_mask = (df["status"] == "ok") & (df["char"] != "")
    if not ok_mask.any():
        pub("done", 0, "没有成功识别的图片")
        _pub_progress(redis, task_id, {"progress": 100, "stage": "done", "message": "没有成功识别的图片", "status": "done", "result": {"total": 0}})
        return {"status": "done", "total": 0}

    ok = df[ok_mask].copy()
    ok["id"] = [uuid_mod.uuid4().hex[:16] for _ in range(len(ok))]
    ok["pinyin"] = ok["char"].astype(str).apply(resolve_pinyin)
    ok["source"] = "dataset_import"
    ok["level"] = metadata.get("level") or "D"
    ok["image_path"] = ok["url"]
    ok["character"] = ok["char"].apply(lambda c: c if c else "?")
    ok["stroke_count"] = ok["char"].apply(lambda c: len(c) if c else 0)
    ok["created_by_user_id"] = metadata.get("user_id", "")

    existing_dataset_id = metadata.get("dataset_id")
    db = db_session_factory()
    try:
        dict_rows = db.execute(
            select(HanziDictionary.character, HanziDictionary.stroke_pattern, HanziDictionary.stroke_count)
        ).all()
        if dict_rows:
            dict_df = pd.DataFrame(dict_rows, columns=["character", "stroke_pattern", "stroke_count"])
            ok = ok.merge(dict_df, on="character", how="left", suffixes=("_orig", "_dict"))
            ok["stroke_count"] = ok["stroke_count_dict"].apply(_safe_int).where(
                ok["stroke_count_dict"].notna() & (ok["stroke_count_dict"] != ""),
                ok["stroke_count_orig"],
            )
            ok["stroke_pattern"] = ok["stroke_pattern"].fillna("")

        # 复用已有数据集或创建新的
        if existing_dataset_id:
            dataset_id = existing_dataset_id
        else:
            dataset_id = uuid_mod.uuid4().hex[:16]
            dataset = HanziDataset(
                id=dataset_id, name=metadata.get("name", f"Import-{task_id[:6]}"),
                level=metadata.get("level") or "D", batch_no=metadata.get("batch_no", ""),
                created_by_user_id=metadata.get("user_id", ""),
            )
            db.add(dataset)
            db.flush()

        hanzi_cols = ["id", "character", "image_path", "stroke_count", "pinyin", "stroke_pattern", "source", "level", "created_by_user_id"]
        hanzi_rows = ok[hanzi_cols].to_dict("records")
        for i in range(0, len(hanzi_rows), BATCH_SIZE):
            db.execute(insert(Hanzi.__table__), hanzi_rows[i:i + BATCH_SIZE])

        item_rows = [
            {"id": uuid_mod.uuid4().hex[:16], "dataset_id": dataset_id, "hanzi_id": row["id"]}
            for row in hanzi_rows
        ]
        for i in range(0, len(item_rows), BATCH_SIZE):
            db.execute(insert(DatasetHanziRelation.__table__), item_rows[i:i + BATCH_SIZE])

        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("DB write failed")
        _pub_progress(redis, task_id, {"progress": 0, "stage": "done", "message": str(e), "status": "failed"})
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()

    saved = len(hanzi_rows)
    pub("done", saved, f"导入完成，共 {saved} 条记录")
    _pub_progress(redis, task_id, {
        "progress": 100, "stage": "done", "message": f"导入完成，共 {saved} 条记录",
        "completed": saved, "total": total, "failed_count": total - saved,
        "status": "done",
        "result": {"total": saved, "failed": total - saved, "dataset_id": dataset_id},
    })

    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

    return {"status": "done", "total": saved, "dataset_id": dataset_id}


def get_import_progress(task_id: str) -> dict | None:
    redis = get_sync_redis()
    raw = redis.get(f"{REDIS_PROGRESS_PREFIX}{task_id}")
    if raw is None:
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return None
