import sys
from pathlib import Path
from richuru import install
from loguru import logger

from .manager import config_manager


def setup_logger():
    """根据配置文件设置loguru日志"""
    install()
    settings = config_manager.get_settings()
    log_config = settings.log
    
    # 移除默认的logger配置
    logger.remove()
    
    # 确保日志目录存在
    log_dir = Path(log_config.file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 设置控制台输出
    if log_config.console_output:
        logger.add(
            sys.stderr,
            format=log_config.format,
            level=log_config.level.value,
            backtrace=log_config.backtrace,
            diagnose=log_config.diagnose,
        )
    
    # 设置主日志文件
    logger.add(
        log_config.file_path,
        format=log_config.format,
        level=log_config.level.value,
        rotation=log_config.rotation,
        retention=log_config.retention,
        compression=log_config.compression,
        backtrace=log_config.backtrace,
        diagnose=log_config.diagnose,
    )
    
    # 设置额外的日志记录器
    for extra_logger in log_config.additional_loggers:
        # 确保额外日志目录存在
        extra_log_dir = Path(extra_logger["file_path"]).parent
        extra_log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            extra_logger["file_path"],
            format=log_config.format,
            level=extra_logger.get("level", log_config.level.value),
            rotation=extra_logger.get("rotation", log_config.rotation),
            retention=extra_logger.get("retention", log_config.retention),
            compression=extra_logger.get("compression", log_config.compression),
            backtrace=log_config.backtrace,
            diagnose=log_config.diagnose,
            filter=extra_logger.get("filter"),
        )
    
    logger.info("日志系统初始化完成")


def get_logger():
    """获取配置好的logger实例"""
    return logger