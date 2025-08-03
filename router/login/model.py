from pydantic import BaseModel, Field
from router.common_model import BaseResponse
from router.invite.model import AuthMeData
from typing import Optional


class LoginRequest(BaseModel):
    userid: str = Field(..., description="学号")
    password: str = Field(..., description="密码")
    easyconnect_password: str = Field(..., description="VPN密码")


# 统一响应模型
class LoginResponse(BaseResponse[AuthMeData]):
    """登录响应"""

    pass


# Authme相关模型
class AuthmeStatusData(BaseModel):
    """认证状态数据"""
    
    is_logged_in: bool = Field(..., description="是否处于登录状态")
    userid: Optional[str] = Field(None, description="用户ID")


class AuthmeResponse(BaseResponse[AuthmeStatusData]):
    """AuthMe验证响应"""
    
    pass