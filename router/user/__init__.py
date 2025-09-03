import base64
from fastapi import Depends
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.creator import get_db_session
from database.user import UserProfile
from provider.loveac.authme import fetch_user_by_token, AuthmeRequest
from utils.file_manager import file_manager
from .model import (
    UserProfileResponse,
    GetUserProfileRequest,
    UpdateUserProfileRequest,
    UserProfileData,
    UserSettings,
)

user_router = APIRouter(prefix="/api/v1/user")


@user_router.post("/profile/get", summary="获取用户资料")
async def get_user_profile(
    data: GetUserProfileRequest,
    asyncsession: AsyncSession = Depends(get_db_session),
):
    """
    获取用户资料
    :param data: GetUserProfileRequest
    :return: UserProfileResponse
    """
    try:
        # 使用token验证获取用户
        authme_request = AuthmeRequest(token=data.token)
        user = await fetch_user_by_token(authme_request, asyncsession)
        
        async with asyncsession as session:
            result = await session.execute(
                select(UserProfile).where(UserProfile.userid == user.userid)
            )
            profile = result.scalars().first()
            
            if not profile:
                # 如果用户资料不存在，创建默认资料
                profile = UserProfile(
                    userid=user.userid,
                    avatar_filename=None,
                    background_filename=None,
                    nickname=None,
                    settings_filename=None
                )
                session.add(profile)
                await session.commit()
            
            # 获取头像数据
            avatar_data = None
            if profile.avatar_filename:
                avatar_bytes = await file_manager.get_avatar(profile.avatar_filename)
                if avatar_bytes:
                    # 转换为base64
                    avatar_data = base64.b64encode(avatar_bytes).decode('utf-8')
                    # 根据文件扩展名添加data URI前缀
                    if profile.avatar_filename.endswith('.png'):
                        avatar_data = f"data:image/png;base64,{avatar_data}"
                    elif profile.avatar_filename.endswith(('.jpg', '.jpeg')):
                        avatar_data = f"data:image/jpeg;base64,{avatar_data}"
                    elif profile.avatar_filename.endswith('.gif'):
                        avatar_data = f"data:image/gif;base64,{avatar_data}"
            
            # 获取背景数据
            background_data = None
            if profile.background_filename:
                background_bytes = await file_manager.get_background(profile.background_filename)
                if background_bytes:
                    # 转换为base64
                    background_data = base64.b64encode(background_bytes).decode('utf-8')
                    # 根据文件扩展名添加data URI前缀
                    if profile.background_filename.endswith('.png'):
                        background_data = f"data:image/png;base64,{background_data}"
                    elif profile.background_filename.endswith(('.jpg', '.jpeg')):
                        background_data = f"data:image/jpeg;base64,{background_data}"
                    elif profile.background_filename.endswith('.gif'):
                        background_data = f"data:image/gif;base64,{background_data}"
                    elif profile.background_filename.endswith('.webp'):
                        background_data = f"data:image/webp;base64,{background_data}"
            
            # 获取设置数据
            settings_data = None
            if profile.settings_filename:
                settings_dict = await file_manager.get_settings(profile.settings_filename)
                if settings_dict:
                    settings_data = UserSettings(**settings_dict)
            
            profile_data = UserProfileData(
                userid=profile.userid,
                avatar=avatar_data,
                background=background_data,
                nickname=profile.nickname,
                settings=settings_data,
            )
            
            return UserProfileResponse(
                code=200,
                message="获取用户资料成功",
                data=profile_data
            )
            
    except Exception as e:
        return UserProfileResponse(
            code=500,
            message=f"获取用户资料失败: {str(e)}",
            data=None
        )


@user_router.post("/profile/update", summary="更新用户资料")
async def update_user_profile(
    data: UpdateUserProfileRequest,
    asyncsession: AsyncSession = Depends(get_db_session),
):
    """
    更新用户资料
    :param data: UpdateUserProfileRequest
    :return: UserProfileResponse
    """
    try:
        # 使用token验证获取用户
        authme_request = AuthmeRequest(token=data.token)
        user = await fetch_user_by_token(authme_request, asyncsession)
        
        async with asyncsession as session:
            result = await session.execute(
                select(UserProfile).where(UserProfile.userid == user.userid)
            )
            profile = result.scalars().first()
            
            if not profile:
                # 如果用户资料不存在，创建新的
                profile = UserProfile(
                    userid=user.userid,
                    avatar_filename=None,
                    background_filename=None,
                    nickname=data.nickname,
                    settings_filename=None
                )
                session.add(profile)
            else:
                # 更新昵称
                if data.nickname is not None:
                    profile.nickname = data.nickname
            
            # 处理头像更新
            if data.avatar is not None:
                if data.avatar:  # 如果头像不为空
                    new_avatar_filename = await file_manager.save_avatar(user.userid, data.avatar)
                    profile.avatar_filename = new_avatar_filename
                else:  # 如果头像为空，表示删除头像
                    if profile.avatar_filename:
                        await file_manager.delete_avatar(profile.avatar_filename)
                    profile.avatar_filename = None
            
            # 处理背景更新
            if data.background is not None:
                if data.background:  # 如果背景不为空
                    new_background_filename = await file_manager.save_background(user.userid, data.background)
                    profile.background_filename = new_background_filename
                else:  # 如果背景为空，表示删除背景
                    if profile.background_filename:
                        await file_manager.delete_background(profile.background_filename)
                    profile.background_filename = None
            
            # 处理设置更新
            if data.settings is not None:
                if data.settings:  # 如果设置不为空
                    # data.settings在model验证时已经被转换为UserSettings对象
                    if isinstance(data.settings, UserSettings):
                        settings_dict = data.settings.model_dump()
                        new_settings_filename = await file_manager.save_settings(user.userid, settings_dict)
                        profile.settings_filename = new_settings_filename
                    else:
                        # 如果不是UserSettings对象，说明验证有问题
                        raise ValueError(f"Settings对象类型错误: {type(data.settings)}")
                else:  # 如果设置为空，表示删除设置
                    if profile.settings_filename:
                        await file_manager.delete_settings(profile.settings_filename)
                    profile.settings_filename = None
            
            await session.commit()
            await session.refresh(profile)
            
            # 获取更新后的数据
            avatar_data = None
            if profile.avatar_filename:
                avatar_bytes = await file_manager.get_avatar(profile.avatar_filename)
                if avatar_bytes:
                    avatar_data = base64.b64encode(avatar_bytes).decode('utf-8')
                    if profile.avatar_filename.endswith('.png'):
                        avatar_data = f"data:image/png;base64,{avatar_data}"
                    elif profile.avatar_filename.endswith(('.jpg', '.jpeg')):
                        avatar_data = f"data:image/jpeg;base64,{avatar_data}"
                    elif profile.avatar_filename.endswith('.gif'):
                        avatar_data = f"data:image/gif;base64,{avatar_data}"
            
            background_data = None
            if profile.background_filename:
                background_bytes = await file_manager.get_background(profile.background_filename)
                if background_bytes:
                    background_data = base64.b64encode(background_bytes).decode('utf-8')
                    if profile.background_filename.endswith('.png'):
                        background_data = f"data:image/png;base64,{background_data}"
                    elif profile.background_filename.endswith(('.jpg', '.jpeg')):
                        background_data = f"data:image/jpeg;base64,{background_data}"
                    elif profile.background_filename.endswith('.gif'):
                        background_data = f"data:image/gif;base64,{background_data}"
                    elif profile.background_filename.endswith('.webp'):
                        background_data = f"data:image/webp;base64,{background_data}"
            
            settings_data = None
            if profile.settings_filename:
                settings_dict = await file_manager.get_settings(profile.settings_filename)
                if settings_dict:
                    settings_data = UserSettings(**settings_dict)
            
            profile_data = UserProfileData(
                userid=profile.userid,
                avatar=avatar_data,
                background=background_data,
                nickname=profile.nickname,
                settings=settings_data,
            )
            
            return UserProfileResponse(
                code=200,
                message="更新用户资料成功",
                data=profile_data
            )
            
    except Exception as e:
        return UserProfileResponse(
            code=500,
            message=f"更新用户资料失败: {str(e)}",
            data=None
        ) 