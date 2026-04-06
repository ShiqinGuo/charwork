import re
from collections import Counter
from pathlib import Path

import pandas as pd


def parse_strokes_file(file_path: str) -> pd.DataFrame:
    """
    功能描述：
        解析strokes文件。

    参数：
        file_path (str): 文件或资源路径。

    返回值：
        pd.DataFrame: 返回pd.DataFrame类型的处理结果。
    """
    path = Path(file_path)
    if not path.exists():
        return pd.DataFrame()

    frame = pd.read_csv(
        path,
        sep="\t",
        engine="python",
        header=None,
        names=["codepoint", "character", "radical", "stroke_count", "stroke_pattern"],
        dtype="string",
    )
    if frame.empty:
        return pd.DataFrame()

    frame["character"] = frame["character"].fillna("").str.strip().str.slice(0, 1)
    frame["stroke_pattern"] = frame["stroke_pattern"].fillna("").str.strip()
    frame["stroke_pattern"] = frame["stroke_pattern"].replace("", pd.NA)
    frame["stroke_count"] = pd.to_numeric(frame["stroke_count"], errors="coerce").astype("Int64")
    frame = frame.loc[frame["character"] != "", ["character", "stroke_count", "stroke_pattern"]]
    frame = frame.drop_duplicates(subset=["character"], keep="last").reset_index(drop=True)
    if frame.empty:
        return pd.DataFrame()

    frame["stroke_count"] = frame["stroke_count"].fillna(frame["stroke_pattern"].str.len()).astype("Int64")
    frame = frame.where(frame.notna(), None)
    return frame


def resolve_pinyin(character: str) -> str:
    """
    功能描述：
        解析pinyin。

    参数：
        character (str): 字符串结果。

    返回值：
        str: 返回解析后的结果数据。
    """
    try:
        from pypinyin import Style, lazy_pinyin

        values = lazy_pinyin(character, style=Style.NORMAL, errors="ignore")
        if values:
            return values[0]
    except Exception:
        pass
    return character


def resolve_pinyin_series(characters: pd.Series) -> pd.Series:
    """
    功能描述：
        解析pinyinseries。

    参数：
        characters (pd.Series): pd.Series 类型的数据。

    返回值：
        pd.Series: 返回解析后的结果数据。
    """
    return characters.fillna("").astype(str).apply(resolve_pinyin)


def normalize_pinyin_keyword(keyword: str | None) -> str:
    """
    功能描述：
        处理pinyinkeyword。

    参数：
        keyword (str | None): 字符串结果。

    返回值：
        str: 返回str类型的处理结果。
    """
    if not keyword:
        return ""
    return re.sub(r"\s+", "", keyword).strip().lower()


def split_stroke_pattern(pattern: str | None) -> list[str]:
    """
    功能描述：
        处理笔画pattern。

    参数：
        pattern (str | None): 字符串结果。

    返回值：
        list[str]: 返回列表形式的结果数据。
    """
    if not pattern:
        return []
    normalized = pattern.replace("，", ",").replace("、", ",").strip()
    if not normalized:
        return []
    if "," in normalized:
        segments = normalized.split(",")
    else:
        segments = re.split(r"\s+", normalized)
    return [segment.strip() for segment in segments if segment and segment.strip()]


def build_stroke_unit_counter(pattern: str | None) -> Counter[str]:
    """
    功能描述：
        构建笔画unitcounter。

    参数：
        pattern (str | None): 字符串结果。

    返回值：
        Counter[str]: 返回构建后的结果对象。
    """
    return Counter(split_stroke_pattern(pattern))


def build_stroke_unit_counts(pattern: str | None) -> dict[str, int]:
    """
    功能描述：
        构建笔画unitcounts。

    参数：
        pattern (str | None): 字符串结果。

    返回值：
        dict[str, int]: 返回字典形式的结果数据。
    """
    return dict(build_stroke_unit_counter(pattern))


def encode_stroke_unit_key(unit: str) -> str:
    """
    功能描述：
        处理笔画unitkey。

    参数：
        unit (str): 字符串结果。

    返回值：
        str: 返回str类型的处理结果。
    """
    return unit.encode("utf-8").hex()


def build_stroke_unit_count_fields(pattern: str | None) -> dict[str, int]:
    """
    功能描述：
        构建笔画unitcount字段。

    参数：
        pattern (str | None): 字符串结果。

    返回值：
        dict[str, int]: 返回字典形式的结果数据。
    """
    return {encode_stroke_unit_key(unit): count for unit, count in build_stroke_unit_counter(pattern).items()}


def contains_exact_stroke_units(candidate_pattern: str | None, query_pattern: str | None) -> bool:
    """
    功能描述：
        处理exact笔画units。

    参数：
        candidate_pattern (str | None): 字符串结果。
        query_pattern (str | None): 字符串结果。

    返回值：
        bool: 返回操作是否成功。
    """
    candidate_counts = build_stroke_unit_counter(candidate_pattern)
    query_counts = build_stroke_unit_counter(query_pattern)
    if not candidate_counts or not query_counts:
        return False
    return all(candidate_counts.get(unit, 0) >= required_count for unit, required_count in query_counts.items())
