from contextlib import asynccontextmanager
from fastapi import FastAPI
from database.creator import db_manager
from router.invite import invite_router
from router.jwc import jwc_router
from router.login import login_router
from router.aac import aac_router
from router.user import user_router
from router.isim import isim_router
from richuru import install
from fastapi.middleware.cors import CORSMiddleware as allow_origins
import uvicorn  
# 导入配置管理器和日志设置
from config import config_manager
from config.logger import setup_logger, get_logger

# 初始化日志系统
install()
setup_logger()
logger = get_logger()




@asynccontextmanager
async def lifespan(app: FastAPI):
    # 验证配置文件完整性
    if not config_manager.validate_config():
        logger.error("配置文件验证失败，请检查配置")
        raise RuntimeError("配置文件验证失败")
    
    logger.info("应用程序启动中...")
    
    # 启动时连接数据库
    await db_manager.init_db()
    logger.success("数据库连接成功")

    yield

    # 关闭时断开数据库连接
    await db_manager.close_db()
    logger.info("应用程序已关闭")


# 获取应用配置
app_config = config_manager.get_settings().app

# Production FastAPI application
app = FastAPI(
    lifespan=lifespan,
    title=app_config.title,
    description=app_config.description,
    version=app_config.version,
    debug=app_config.debug,
    docs_url=None if not app_config.debug else "/docs",
    redoc_url=None if not app_config.debug else "/redoc",
    openapi_url=None if not app_config.debug else "/openapi.json",  
)

# CORS配置
app.add_middleware(
    allow_origins,
    allow_origins=app_config.cors_allow_origins,
    allow_credentials=app_config.cors_allow_credentials,
    allow_methods=app_config.cors_allow_methods,
    allow_headers=app_config.cors_allow_headers,
)

@app.get("/")
async def root():
    return {"message": "Hello World"}

app.include_router(invite_router)
app.include_router(jwc_router)
app.include_router(login_router)
app.include_router(aac_router)
app.include_router(user_router)
app.include_router(isim_router)

if __name__ == "__main__":
    uvicorn.run(app, host=app_config.host, port=app_config.port)