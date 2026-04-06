from app.services.stroke_service import StrokeService


# 在模块加载时创建单例，避免每次请求重复初始化笔画服务造成额外 I/O 开销。
stroke_service = StrokeService()
