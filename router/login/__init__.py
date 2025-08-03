from fastapi import Depends
from fastapi.routing import APIRouter
from database.user import User
from database.creator import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from router.login.model import (
    LoginRequest,
    LoginResponse,
    AuthmeResponse,
    AuthmeStatusData,
)
from router.invite.model import AuthMeData
from provider.aufe.client import AUFEConnection
from provider.loveac.authme import manage_user_tokens, generate_device_id, fetch_user_by_token, AuthmeRequest
import secrets

login_router = APIRouter(prefix="/api/v1/user")


@login_router.post("/login", summary="用户登录")
async def login_user(
    data: LoginRequest, asyncsession: AsyncSession = Depends(get_db_session)
) -> LoginResponse:
    """
    用户登录
    :param data: LoginRequest
    :return: LoginResponse
    """
    async with asyncsession as session:
        userid = data.userid
        password = data.password
        easyconnect_password = data.easyconnect_password

        # 检查用户是否存在
        existing_user = await session.execute(select(User).where(User.userid == userid))
        user = existing_user.scalars().first()
        if not user:
            return LoginResponse(
                code=400,
                message="用户不存在",
                data=None,
            )

        # 检查连接
        vpn = AUFEConnection.create_or_get_connection("vpn.aufe.edu.cn", userid)
        # 检查连接是否已经存在，避免重复登录
        if not vpn.login_status():
            if not await vpn.login(userid, easyconnect_password):
                return LoginResponse(
                    code=400,
                    message="VPN登录失败，请检查用户名和密码",
                    data=None,
                )
        if not vpn.uaap_login_status():
            if not await vpn.uaap_login(userid, password):
                return LoginResponse(
                    code=400,
                    message="大学登录失败，请检查用户名和密码",
                    data=None,
                )

        # 生成新的token和设备ID
        authme_token = secrets.token_urlsafe(128)
        device_id = generate_device_id()
        
        # 使用新的token管理系统
        await manage_user_tokens(userid, authme_token, device_id, session)

        return LoginResponse(
            code=200,
            message="登录成功",
            data=AuthMeData(authme_token=authme_token),
        )


@login_router.post("/authme", summary="验证登录状态")
async def check_auth_status(
    data: AuthmeRequest, asyncsession: AsyncSession = Depends(get_db_session)
) -> AuthmeResponse:
    """
    验证token是否有效，返回登录状态
    :param data: AuthmeRequest
    :return: AuthmeResponse
    """
    try:
        # 使用已有的fetch_user_by_token函数验证token
        user = await fetch_user_by_token(data, asyncsession)
        
        return AuthmeResponse(
            code=200,
            message="验证成功",
            data=AuthmeStatusData(
                is_logged_in=True,
                userid=user.userid
            ),
        )
    except Exception as e:
        # token无效或其他错误
        return AuthmeResponse(
            code=401,
            message="token无效或已过期",
            data=AuthmeStatusData(
                is_logged_in=False,
                userid=None
            ),
        )


