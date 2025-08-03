try:
    from .s3_client import s3_client
    __all__ = ["s3_client"]
except ImportError:
    # 如果S3客户端依赖不可用，则不导出
    __all__ = []