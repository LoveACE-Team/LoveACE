from fastapi import Depends, HTTPException
from provider.loveac.authme import fetch_user_by_token
from provider.aufe.jwc import JWCClient
from provider.aufe.client import AUFEConnection
from database.user import User


async def get_jwc_client(
    user: User = Depends(fetch_user_by_token),
) -> JWCClient:
    """
    获取教务处客户端
    :param authme_request: AuthmeRequest
    :return: JWCClient
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
    return JWCClient(aufe)
