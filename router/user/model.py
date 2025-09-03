from pydantic import BaseModel, Field, field_validator
from router.common_model import BaseResponse
from typing import Optional, Union
import json


class UserSettings(BaseModel):
    """用户设置模型"""
    theme: str = Field(..., description="主题模式")
    lightModeOpacity: float = Field(..., description="浅色模式透明度", ge=0.0, le=1.0)
    lightModeBrightness: float = Field(..., description="浅色模式亮度", ge=0.0, le=1.0)
    darkModeOpacity: float = Field(..., description="深色模式透明度", ge=0.0, le=1.0)
    darkModeBrightness: float = Field(..., description="深色模式亮度", ge=0.0, le=1.0)
    backgroundBlur: float = Field(..., description="背景模糊强度", ge=0.0, le=1.0)
    
    @field_validator('theme')
    def validate_theme(cls, v):
        """验证主题值"""
        valid_themes = ['light', 'dark', 'system', 'ThemeMode.light', 'ThemeMode.dark', 'ThemeMode.system']
        if v not in valid_themes:
            raise ValueError(f"无效的主题值: {v}，有效值: {valid_themes}")
        return v


class UserProfileData(BaseModel):
    """用户资料数据模型"""
    userid: str = Field(..., description="用户ID")
    avatar: Optional[str] = Field(None, description="用户头像base64数据")
    background: Optional[str] = Field(None, description="用户背景base64数据")
    nickname: Optional[str] = Field(None, description="用户昵称")
    settings: Optional[UserSettings] = Field(None, description="用户设置对象")


class GetUserProfileRequest(BaseModel):
    """获取用户资料请求模型"""
    token: str = Field(..., description="用户认证token")


class UpdateUserProfileRequest(BaseModel):
    """更新用户资料请求模型"""
    token: str = Field(..., description="用户认证token")
    avatar: Optional[str] = Field(None, description="用户头像base64编码数据")
    background: Optional[str] = Field(None, description="用户背景base64编码数据")
    nickname: Optional[str] = Field(None, description="用户昵称")
    settings: Optional[Union[UserSettings, str]] = Field(None, description="用户设置对象或JSON字符串")
    
    @field_validator('settings')
    def parse_settings(cls, v):
        """解析settings字段，支持字符串和对象两种格式"""
        if v is None:
            return v
        
        # 如果已经是UserSettings对象，直接返回
        if isinstance(v, UserSettings):
            return v
        
        # 如果是字符串，尝试解析为JSON然后创建UserSettings对象
        if isinstance(v, str):
            try:
                settings_dict = json.loads(v)
                return UserSettings(**settings_dict)
            except json.JSONDecodeError as e:
                raise ValueError(f"settings字段JSON格式错误: {str(e)}")
            except Exception as e:
                raise ValueError(f"settings字段验证失败: {str(e)}")
        
        # 如果是字典，直接创建UserSettings对象
        if isinstance(v, dict):
            try:
                return UserSettings(**v)
            except Exception as e:
                raise ValueError(f"settings字段验证失败: {str(e)}")
        
        raise ValueError("settings字段必须是JSON字符串、字典或UserSettings对象")


class UserProfileResponse(BaseResponse[UserProfileData]):
    """用户资料响应模型"""
    pass 