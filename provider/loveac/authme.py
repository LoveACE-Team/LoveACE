import json
import uuid
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database.creator import get_db_session
from database.user import User, AuthME
from sqlalchemy import select, desc
from pydantic import BaseModel
from loguru import logger
from typing import Optional


class AuthmeRequest(BaseModel):
    token: str


class AuthmeResponse(BaseModel):
    code: int
    message: str


async def fetch_user_by_token(
    AuthmeRequest: AuthmeRequest, 
    asyncsession: AsyncSession = Depends(get_db_session)
) -> User:
    """
    根据令牌获取用户信息
    :param AuthmeRequest: 包含token的请求对象
    :param asyncsession: 数据库会话
    :return: User
    """
    async with asyncsession as session:
        # 根据token查找AuthME记录
        result = await session.execute(
            select(AuthME).where(AuthME.authme_token == AuthmeRequest.token)
        )
        authme = result.scalars().first()
        
        if not authme:
            raise HTTPException(status_code=401, detail="无效的令牌或用户不存在")
        
        # 根据userid获取用户信息
        user_result = await session.execute(
            select(User).where(User.userid == authme.userid)
        )
        user = user_result.scalars().first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")

        logger.info(f"User {user.userid} fetched successfully using token.")
        return user


async def manage_user_tokens(userid: str, new_token: str, device_id: str, session: AsyncSession) -> None:
    """
    管理用户token，每个用户最多保持5个设备会话，超出时删除最旧的2个
    :param userid: 用户ID
    :param new_token: 新的token
    :param device_id: 设备标识符
    :param session: 数据库会话
    """
    # 检查当前用户的token数量
    result = await session.execute(
        select(AuthME)
        .where(AuthME.userid == userid)
        .order_by(desc(AuthME.create_date))
    )
    existing_tokens = result.scalars().all()
    
    # 如果超过4个token（即将添加第6个），删除最旧的2个
    if len(existing_tokens) >= 5:
        # 删除最旧的2个token
        oldest_tokens = existing_tokens[-2:]
        for token_record in oldest_tokens:
            await session.delete(token_record)
    
    # 添加新的token记录
    new_authme = AuthME(
        userid=userid,
        authme_token=new_token,
        device_id=device_id
    )
    session.add(new_authme)
    await session.commit()


def generate_device_id() -> str:
    """生成设备标识符"""
    return str(uuid.uuid4())
