"""
为什么这样做：笔画服务在启动时一次性加载文件，避免高频查询反复 IO。
特殊逻辑：同时兼容“|”与制表符两种历史格式，解析失败行直接跳过作为脏数据边界兜底。
"""

import os
from typing import Dict

from app.core.config import settings


class StrokeService:
    def __init__(self):
        """
        初始化stroke_data。
        """
        self._stroke_data: Dict[str, str] = {}

    def load(self) -> None:
        """
        功能描述：
            加载StrokeService。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        path = settings.STROKES_FILE_PATH
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        if not os.path.exists(path):
            self._stroke_data = {}
            return
        data: Dict[str, str] = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                if "|" in raw:
                    parts = raw.split("|")
                    if len(parts) >= 3:
                        ch = parts[1]
                        try:
                            count = int(parts[2])
                            data[ch] = "*" * count
                        except ValueError:
                            continue
                    continue
                parts = raw.split("\t")
                if len(parts) >= 5:
                    ch = parts[1]
                    strokes = parts[4]
                    data[ch] = strokes
        self._stroke_data = data

    def get_stroke_order(self, ch: str) -> str:
        """
        功能描述：
            按条件获取笔画order。

        参数：
            ch (str): 字符串结果。

        返回值：
            str: 返回查询到的结果对象。
        """
        return self._stroke_data.get(ch, "")

    def get_stroke_count(self, ch: str) -> int:
        """
        功能描述：
            按条件获取笔画count。

        参数：
            ch (str): 字符串结果。

        返回值：
            int: 返回查询到的结果对象。
        """
        order = self.get_stroke_order(ch)
        return len(order) if order else 0

    def match_pattern(self, order: str, pattern: str) -> bool:
        """
        功能描述：
            处理pattern。

        参数：
            order (str): 字符串结果。
            pattern (str): 字符串结果。

        返回值：
            bool: 返回操作是否成功。
        """
        if not pattern:
            return False
        tokens = [p.strip() for p in pattern.split(" ") if p.strip()]
        return all(t in order for t in tokens)
