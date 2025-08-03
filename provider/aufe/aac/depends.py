from fastapi import Depends, HTTPException
from loguru import logger
from provider.loveac.authme import fetch_user_by_token
from provider.aufe.aac import AACClient, get_system_token
from provider.aufe.client import AUFEConnection
from database.user import User, AACTicket
from sqlalchemy.ext.asyncio import AsyncSession
from database.creator import get_db_session
from sqlalchemy import select


async def get_aac_client(
    user: User = Depends(fetch_user_by_token),
    db: AsyncSession = Depends(get_db_session),
) -> AACClient:
    """
    获取AAC客户端
    :param user: 用户信息
    :return: AACClient
    :raises HTTPException: 如果用户无效或登录失败
    """

    if not user:
        raise HTTPException(status_code=400, detail="无效的令牌或用户不存在")
    aufe = AUFEConnection.create_or_get_connection("vpn.aufe.edu.cn", user.userid)
    if not aufe.login_status():
        userid = user.userid
        easyconnect_password = user.easyconnect_password
        if not await aufe.login(userid, easyconnect_password):
            raise HTTPException(
                status_code=400,
                detail="VPN登录失败，请检查用户名和密码",
            )
    if not aufe.uaap_login_status():
        userid = user.userid
        password = user.password
        if not await aufe.uaap_login(userid, password):
            raise HTTPException(
                status_code=400,
                detail="大学登录失败，请检查用户名和密码",
            )
    # 检查AAC Ticket是否存在
    async with db as session:
        result = await session.execute(
            select(AACTicket).where(AACTicket.userid == user.userid)
        )
        aac_ticket = result.scalars().first()
    if not aac_ticket:
        # 如果不存在，尝试获取新的AAC Ticket
        logger.info(f"用户 {user.userid} 的 AAC Ticket 不存在，正在获取新的 Ticket")
        aac_ticket = await get_system_token(aufe)
        if not aac_ticket:
            logger.error(f"用户 {user.userid} 获取 AAC Ticket 失败")
            raise HTTPException(
                status_code=400,
                detail="获取AAC Ticket失败，请稍后再试",
            )
        # 保存到数据库
        async with db as session:
            session.add(AACTicket(userid=user.userid, aac_token=aac_ticket))
            await session.commit()
        logger.success(f"用户 {user.userid} 成功获取并保存新的 AAC Ticket")
    else:
        logger.info(f"用户 {user.userid} 使用现有的 AAC Ticket")
        aac_ticket = aac_ticket.aac_token
    return AACClient(aufe, aac_ticket)
