from pydantic import BaseModel, Field
from router.common_model import BaseResponse


class InviteRequest(BaseModel):
    invite_code: str = Field(..., description="邀请码")


class RegisterRequest(BaseModel):
    userid: str = Field(..., description="学号")
    password: str = Field(..., description="密码")
    easyconnect_password: str = Field(..., description="易联密码")
    invite_token: str = Field(..., description="邀请码")


# 邀请相关响应数据模型
class InviteTokenData(BaseModel):
    """邀请令牌数据"""

    invite_token: str = Field(..., description="邀请密钥")


class AuthMeData(BaseModel):
    """认证令牌数据"""

    authme_token: str = Field(..., description="AuthMe Token")


# 统一响应模型
class InviteResponse(BaseResponse[InviteTokenData]):
    """邀请响应"""

    pass


class RegisterResponse(BaseResponse[AuthMeData]):
    """注册响应"""

    pass
