from fastapi import Depends
from fastapi.routing import APIRouter
from database.user import Invite, User
from database.creator import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from router.invite.model import (
    InviteRequest,
    RegisterRequest,
    InviteResponse,
    RegisterResponse,
    InviteTokenData,
    AuthMeData,
)
from provider.aufe.client import AUFEConnection
from database.user import AuthME
import secrets

invite_router = APIRouter(prefix="/api/v1/user")
invite_tokens = []


@invite_router.post("/veryfy_invite_code", summary="验证邀请码")
async def verify_invite_code(
    data: InviteRequest,
    asyncsession: AsyncSession = Depends(get_db_session),
) -> InviteResponse:
    """
    验证邀请码
    :param  data: InviteRequest
    :return: InviteResponse
    """
    async with asyncsession as session:
        invite_code = data.invite_code
        invite = select(Invite).where(Invite.invite_code == invite_code)
        result = await session.execute(invite)
        invite_data = result.scalars().first()
        if invite_data:
            invite_token = secrets.token_urlsafe(128)
            invite_tokens.append(invite_token)
            return InviteResponse(
                code=200,
                message="邀请码验证成功",
                data=InviteTokenData(invite_token=invite_token),
            )
        else:
            return InviteResponse(
                code=400,
                message="邀请码无效或已过期",
                data=None,
            )


@invite_router.post("/register", summary="注册新用户")
async def register_user(
    data: RegisterRequest,
    asyncsession: AsyncSession = Depends(get_db_session),
) -> RegisterResponse:
    """
    注册新用户
    :param data: RegisterRequest
    :return: RegisterResponse
    """
    async with asyncsession as session:
        userid = data.userid
        password = data.password
        easyconnect_password = data.easyconnect_password
        invite_token = data.invite_token
        if invite_token not in invite_tokens:
            return RegisterResponse(
                code=400,
                message="无效的邀请令牌",
                data=None,
            )

        # 检查用户是否已存在
        existing_user = await session.execute(select(User).where(User.userid == userid))
        if existing_user.scalars().first():
            return RegisterResponse(
                code=400,
                message="用户已存在",
                data=None,
            )

        # 检查连接
        vpn = AUFEConnection.create_or_get_connection("vpn.aufe.edu.cn", userid)
        if not await vpn.login(userid, easyconnect_password):
            return RegisterResponse(
                code=400,
                message="VPN登录失败，请检查用户名和密码",
                data=None,
            )

        if not await vpn.uaap_login(userid, password):
            return RegisterResponse(
                code=400,
                message="大学登录失败，请检查用户名和密码",
                data=None,
            )
        # 创建新用户

        new_user = User(
            userid=userid,
            password=password,
            easyconnect_password=easyconnect_password,
        )
        session.add(new_user)
        await session.commit()
        authme_token = secrets.token_urlsafe(128)
        new_authme = AuthME(userid=userid, authme_token=authme_token)
        session.add(new_authme)
        await session.commit()
        invite_tokens.remove(invite_token)
        return RegisterResponse(
            code=200,
            message="注册成功",
            data=AuthMeData(authme_token=authme_token),
        )
