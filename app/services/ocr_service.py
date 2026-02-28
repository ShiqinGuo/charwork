import logging
import os
import time
import requests

from hashlib import md5
from typing import Any, Optional

from urllib.parse import urlencode
from starlette.concurrency import run_in_threadpool
from volcengine.imagex.v2.imagex_service import ImagexService

from app.core.config import settings
from app.utils.image_utils import merge_images


logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self):
        # 原有火山引擎配置（保留，不影响原有逻辑）
        self.volcengine_access_key = settings.VOLCENGINE_ACCESS_KEY_ID.strip()
        self.volcengine_secret_key = settings.VOLCENGINE_SECRET_ACCESS_KEY.strip()
        self.volcengine_region = settings.VOLCENGINE_REGION
        self.volcengine_service_id = settings.VOLCENGINE_SERVICE_ID.strip()
        self.volcengine_default_scene = settings.IMAGEX_DEFAULT_SCENE.strip()
        self.volcengine_workflow_template_id = "system_workflow_image_ocr"

        self.imagex_service = ImagexService(region=self.volcengine_region)
        if self.volcengine_access_key:
            self.imagex_service.set_ak(self.volcengine_access_key)
        if self.volcengine_secret_key:
            self.imagex_service.set_sk(self.volcengine_secret_key)

        self.baidu_api_key = settings.BAIDU_API_KEY.strip()
        self.baidu_secret_key = settings.BAIDU_SECRET_KEY.strip()
        # token缓存与过期时间（提前过期，避免临界值调用失败）
        self._baidu_access_token: str | None = None
        self._baidu_access_token_expires_at: float = 0.0
        self._baidu_token_advance_expire = 300

    def _default_store_key(self, image_path: str) -> str:
        ext = os.path.splitext(image_path)[1].lower() or ".png"
        with open(image_path, "rb") as f:
            digest = md5(f.read()).hexdigest()
        return f"ocr/{digest}{ext}"

    def _upload_image(self, image_path: str, store_key: Optional[str] = None) -> dict[str, Any]:
        if not os.path.isfile(image_path):
            raise ValueError("图片文件不存在")
        if not self.volcengine_service_id:
            raise ValueError("缺少 ImageX 服务编号，请配置 IMAGEX_SERVICE_ID")

        store_key = self._default_store_key(image_path)
        params = {
            "ServiceId": self.volcengine_service_id,
            "StoreKeys": [store_key],
            "Overwrite": True,
        }
        res = self.imagex_service.upload_image(params, [image_path])
        return {"URI": res.get("Results", [{}])[0].get("Uri", ""), "StoreKey": store_key, "raw": res}

    def _transform_uri2url(self, uri: str) -> str:
        """将 ImageX URI 转换为可公网访问的URL（供百度OCR拉取图片）"""
        params = {
            "ServiceId": self.volcengine_service_id,
            "Domain": settings.IMAGEX_DEFAULT_DOMAIN,
            "URI": uri,
            "Tpl": settings.IMAGEX_TEMPLATE_ID,
        }
        return self.imagex_service.get_resource_url(params).get("Result", {}).get("URL", "")

    def _get_baidu_access_token(self) -> str:
        if self._baidu_access_token and (
            time.time() < self._baidu_access_token_expires_at - self._baidu_token_advance_expire
        ):
            return self._baidu_access_token

        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.baidu_api_key,
            "client_secret": self.baidu_secret_key
        }
        resp = requests.post(url, params=params)

        self._baidu_access_token = str(resp.json().get("access_token"))
        self._baidu_access_token_expires_at = time.time() + int(resp.json().get("expires_in", 0))

        return self._baidu_access_token

    def _ai_process_ocr(self, image_url: str) -> dict[str, Any]:
        """
        调用百度OCR接口，完成图片识别流程
        :param image_url: 图片公网可访问URL
        :return: 百度OCR完整返回结果
        """
        url = "https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting?access_token=" + self._get_baidu_access_token()

        payload = {
            "url": image_url,
            "detect_direction": "true",
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }

        response = requests.post(url, headers=headers, data=urlencode(payload), timeout=30)
        response.raise_for_status()
        result = response.json()

        return result

    def _extract_text(self, payload: Any) -> str | list[str]:
        """
        提取文字，并顺时针90度旋转重组
        :param payload: 百度OCR返回结果
        :return: 重组后的全文本 / 单字符列表
        """
        if not isinstance(payload, dict):
            return ""

        words_result = payload.get("words_result", [])
        if not words_result:
            return ""

        raw_lines = [item.get("words", "") for item in words_result]
        if not any(raw_lines):
            return ""

        full_text = "".join(["".join(row).replace(" ", "") for row in raw_lines])

        if len(full_text) == 1:
            return full_text
        return [char for char in full_text]

    async def recognize_image(self, image_path: str) -> str | list[str]:
        """
        识别单张图片，对外核心调用方法（已切换为百度OCR）
        :param image_path: 本地图片路径
        :return: 识别结果（单字符str/多字符list）
        """
        # 校验百度OCR配置
        if not self.baidu_api_key or not self.baidu_secret_key:
            raise ValueError("缺少百度OCR凭证，请配置 BAIDU_API_KEY/BAIDU_SECRET_KEY")
        # 校验图片上传所需的火山配置
        if not self.volcengine_service_id or not self.volcengine_access_key or not self.volcengine_secret_key:
            raise ValueError("缺少火山引擎图片上传凭证，请检查相关配置")

        def _work() -> str | list[str]:
            # 上传图片到火山，获取公网URL
            upload_res = self._upload_image(image_path)
            uri = upload_res.get("URI", "")
            image_url = self._transform_uri2url(uri)
            if not image_url:
                raise ValueError("图片URL生成失败，请检查火山引擎配置")

            # 调用百度OCR识别
            ocr_result = self._ai_process_ocr(image_url)
            # 提取文本结果
            return self._extract_text(ocr_result)

        return await run_in_threadpool(_work)

    async def recognize(self, image_path: str) -> dict[str, Any]:
        """识别单张图片中的字符，返回单个字符"""
        char = await self.recognize_image(image_path)
        return {"characters": char, "image_path": image_path}

    async def batch_recognize(self, image_paths: list[str]) -> dict[str, Any]:
        """批量识别多张图片中的字符，返回字符列表"""
        merged_paths = await run_in_threadpool(merge_images, image_paths)
        char_list = []
        for merged_path in merged_paths:
            res = await self.recognize_image(merged_path)
            char_list.extend(res if isinstance(res, list) else [res])
        return {"character": char_list, "merged_paths": merged_paths}
