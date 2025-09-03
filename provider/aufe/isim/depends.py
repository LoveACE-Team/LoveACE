from fastapi import Depends, HTTPException
from database.creator import get_db_session
from provider.loveac.authme import fetch_user_by_token
from provider.aufe.isim import ISIMClient
from provider.aufe.client import AUFEConnection
from database.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from database.isim import ISIMRoomBinding
from sqlalchemy import select


# 全局ISIM客户端池
_isim_clients: Dict[str, ISIMClient] = {}

def get_cached_isim_client(user_id: str) -> ISIMClient:
    """
    获取缓存的ISIM客户端
    
    Args:
        user_id: 用户ID
        
    Returns:
        ISIMClient: 缓存的ISIM客户端实例，如果未找到则返回None
    """
    return _isim_clients.get(user_id)

def cache_isim_client(user_id: str, client: ISIMClient) -> None:
    """
    缓存ISIM客户端
    
    Args:
        user_id: 用户ID
        client: ISIM客户端实例
    """
    _isim_clients[user_id] = client


async def get_isim_client(
    user: User = Depends(fetch_user_by_token),
    session: AsyncSession = Depends(get_db_session),
) -> ISIMClient:
    from loguru import logger
    """
    获取ISIM客户端实例
    
    Args:
        user: 用户对象（通过认证令牌获取）
        
    Returns:
        ISIMClient: ISIM客户端实例
        
    Raises:
        HTTPException: 认证失败时抛出
    """
    if not user:
        raise HTTPException(status_code=400, detail="无效的令牌或用户不存在")
    
    # 首先检查是否已有缓存的ISIM客户端
    cached_client = get_cached_isim_client(user.userid)
    if cached_client:
        # 检查缓存的客户端是否仍然有效
        try:
            if cached_client.is_session_valid():
                from loguru import logger
                logger.info(f"复用缓存的ISIM客户端: user_id={user.userid}")
                return cached_client
        except Exception as e:
            from loguru import logger
            logger.warning(f"缓存的ISIM客户端无效，将重新创建: {str(e)}")
    
    # 创建或获取VPN连接
    aufe = AUFEConnection.create_or_get_connection("vpn.aufe.edu.cn", user.userid)
    
    # 检查VPN登录状态
    if not aufe.login_status():
        userid = user.userid
        easyconnect_password = user.easyconnect_password
        if not await aufe.login(userid, easyconnect_password):
            raise HTTPException(
                status_code=400,
                detail="VPN登录失败，请检查用户名和密码",
            )
    
    # 检查UAAP登录状态
    if not aufe.uaap_login_status():
        userid = user.userid
        password = user.password
        if not await aufe.uaap_login(userid, password):
            raise HTTPException(
                status_code=400,
                detail="大学登录失败，请检查用户名和密码",
            )
    
    # 创建新的ISIM客户端
    isim_client = ISIMClient(aufe)


    result_query = await session.execute(
            select(ISIMRoomBinding).where(ISIMRoomBinding.userid == user.userid)
        )
    binding_record = result_query.scalars().first()
    if binding_record:
        logger.info(f"找到用户({user.userid})绑定记录，进行启动再绑定")
        await isim_client.bind_room(
                building_code=binding_record.building_code,
                floor_code=binding_record.floor_code,
                room_code=binding_record.room_code,
            )
    
    # 缓存客户端
    cache_isim_client(user.userid, isim_client)

    logger.info(f"创建并缓存新的ISIM客户端: user_id={user.userid}")
    
    return isim_client
