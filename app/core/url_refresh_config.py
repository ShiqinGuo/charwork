"""
ImageX URL 刷新表级注册配置。

新增需要刷新的表只需添加一条字典条目，字段说明：
- url_field: 存储签名 URL 的字段名
- uri_field: 存储 veImageX URI 的字段名
- enabled:  是否对该表启用刷新
"""

from app.models.attachment import Attachment
from app.models.hanzi import Hanzi

URL_REFRESH_TABLE_CONFIG: dict[type, dict[str, object]] = {
    Attachment: {
        "url_field": "file_url",
        "uri_field": "uri",
        "enabled": True,
    },
    Hanzi: {
        "url_field": "image_path",
        "uri_field": "uri",
        "enabled": True,
    },
}
