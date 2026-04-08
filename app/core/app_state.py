"""
应用全局状态模块。

在模块加载时创建单例服务实例，避免每次请求重复初始化造成额外 I/O 开销。
"""

from app.services.stroke_service import StrokeService

# 笔画数据服务单例
stroke_service = StrokeService()
