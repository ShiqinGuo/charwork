from typing import Optional


def resolve_pagination(
    page: Optional[int] = None,
    size: Optional[int] = None,
    skip: Optional[int] = None,
    limit: Optional[int] = None,
    default_limit: int = 20,
    max_limit: int = 100,
) -> dict:
    """
    功能描述：
        解析分页。

    参数：
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        default_limit (int): 整数结果。
        max_limit (int): 整数结果。

    返回值：
        dict: 返回字典形式的结果数据。
    """
    if page is not None or size is not None:
        # 当调用方提供 page/size 时优先走页码语义，避免与 skip/limit 混用导致查询窗口漂移。
        normalized_page = page if page and page > 0 else 1
        normalized_size = size if size and size > 0 else default_limit
        # 统一做上限裁剪，防止大页请求在权限过滤后仍造成数据库压力突增。
        normalized_size = min(normalized_size, max_limit)
        normalized_skip = (normalized_page - 1) * normalized_size
        normalized_limit = normalized_size
    else:
        normalized_skip = skip if skip is not None and skip >= 0 else 0
        normalized_limit = limit if limit is not None and limit > 0 else default_limit
        normalized_limit = min(normalized_limit, max_limit)
        normalized_page = (normalized_skip // normalized_limit) + 1
        normalized_size = normalized_limit

    return {
        "page": normalized_page,
        "size": normalized_size,
        "skip": normalized_skip,
        "limit": normalized_limit,
    }


def build_paged_response(items: list, total: int, pagination: dict) -> dict:
    """
    功能描述：
        构建paged响应。

    参数：
        items (list): 当前处理的实体对象列表。
        total (int): 整数结果。
        pagination (dict): 字典形式的结果数据。

    返回值：
        dict: 返回字典形式的结果数据。
    """
    return {
        "total": total,
        "items": items,
        "page": pagination["page"],
        "size": pagination["size"],
        "skip": pagination["skip"],
        "limit": pagination["limit"],
        "has_more": pagination["skip"] + len(items) < total,
    }
