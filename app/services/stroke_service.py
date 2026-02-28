import os
from typing import Dict

from app.core.config import settings


class StrokeService:
    def __init__(self):
        self._stroke_data: Dict[str, str] = {}

    def load(self) -> None:
        path = settings.STROKES_FILE_PATH
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        if not os.path.exists(path):
            self._stroke_data = {}
            return
        data: Dict[str, str] = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 5:
                    ch = parts[1]
                    strokes = parts[4]
                    data[ch] = strokes
        self._stroke_data = data

    def get_stroke_order(self, ch: str) -> str:
        return self._stroke_data.get(ch, "")

    def get_stroke_count(self, ch: str) -> int:
        order = self.get_stroke_order(ch)
        return len(order) if order else 0

    def match_pattern(self, order: str, pattern: str) -> bool:
        if not pattern:
            return False
        tokens = [p.strip() for p in pattern.split(" ") if p.strip()]
        return all(t in order for t in tokens)
