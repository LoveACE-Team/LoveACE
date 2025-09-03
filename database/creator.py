from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from .base import Base
from config import config_manager
from loguru import logger


class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.async_session_maker = None
        self._config = None

    def _get_db_config(self):
        """获取数据库配置"""
        if self._config is None:
            self._config = config_manager.get_settings().database
        return self._config

    async def init_db(self):
        """初始化数据库连接"""
        db_config = self._get_db_config()
        
        logger.info("正在初始化数据库连接...")
        try:
            self.engine = create_async_engine(
                db_config.url,
                echo=db_config.echo,
                pool_size=db_config.pool_size,
                max_overflow=db_config.max_overflow,
                pool_timeout=db_config.pool_timeout,
                pool_recycle=db_config.pool_recycle,
                future=True
            )

        
            self.async_session_maker = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )

        # 创建所有表
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            logger.error(f"数据库连接初始化失败: {e}")
            logger.error(f"数据库连接URL: {db_config.url}")
            logger.error(f"数据库连接配置: {db_config}")
            logger.error("请启动config_tui.py来配置数据库连接")
            raise 
        logger.info("数据库连接初始化完成")

    async def close_db(self):
        """关闭数据库连接"""
        if self.engine:
            logger.info("正在关闭数据库连接...")
            await self.engine.dispose()
            logger.info("数据库连接已关闭")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        if not self.async_session_maker:
            raise RuntimeError("Database not initialized. Call init_db() first.")

        async with self.async_session_maker() as session:
            try:
                yield session
            finally:
                await session.close()


# 全局数据库管理器实例
db_manager = DatabaseManager()


# FastAPI 依赖函数
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖函数，用于FastAPI路由"""
    async for session in db_manager.get_session():
        yield session
