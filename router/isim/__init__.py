from fastapi import Depends
from fastapi.routing import APIRouter
from provider.aufe.isim import ISIMClient
from provider.aufe.isim.depends import get_isim_client
from provider.loveac.authme import AuthmeResponse
from router.isim.model import (
    BuildingListResponse,
    FloorListResponse,
    RoomListResponse,
    RoomBindingResponse,
    ElectricityInfoResponse,
    PaymentInfoResponse,
    RoomBindingStatusData,
    RoomBindingStatusResponse,
)
from router.common_model import ErrorResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from database.creator import get_db_session
from database.isim import ISIMRoomBinding
from sqlalchemy import select, update
from pydantic import BaseModel
from provider.aufe.isim.model import BuildingInfo, FloorInfo, RoomInfo, RoomBindingInfo


# 简化的请求模型，只需要业务参数
class SetBuildingRequest(BaseModel):
    building_code: str


class SetFloorRequest(BaseModel):
    floor_code: str


class SetRoomRequest(BaseModel):
    building_code: str
    floor_code: str
    room_code: str


isim_router = APIRouter(prefix="/api/v1/isim")


# ==================== 房间选择器API ====================


@isim_router.post(
    "/picker/building/get",
    summary="获取楼栋列表",
    response_model=BuildingListResponse | AuthmeResponse | ErrorResponse,
)
async def get_building_list(client: ISIMClient = Depends(get_isim_client)):
    """获取所有可选楼栋列表"""
    try:
        result = await client.get_buildings()

        response = BuildingListResponse.from_data(
            data=result,
            success_message="楼栋列表获取成功",
            error_message="获取楼栋列表失败，网络请求多次重试后仍无法连接后勤系统，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        logger.error(f"获取楼栋列表时发生系统错误: {str(e)}")
        return ErrorResponse(message=f"获取楼栋列表时发生系统错误：{str(e)}", code=500)


@isim_router.post(
    "/picker/building/set",
    summary="设置楼栋并获取楼层列表",
    response_model=FloorListResponse | AuthmeResponse | ErrorResponse,
)
async def set_building_get_floors(
    request: SetBuildingRequest, client: ISIMClient = Depends(get_isim_client)
):
    """设置楼栋并获取对应的楼层列表"""
    try:
        result = await client.get_floors(request.building_code)

        response = FloorListResponse.from_data(
            data=result,
            success_message="楼层列表获取成功",
            error_message="获取楼层列表失败，网络请求多次重试后仍无法连接后勤系统，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        logger.error(f"获取楼层列表时发生系统错误: {str(e)}")
        return ErrorResponse(message=f"获取楼层列表时发生系统错误：{str(e)}", code=500)


@isim_router.post(
    "/picker/floor/set",
    summary="设置楼层并获取房间列表",
    response_model=RoomListResponse | AuthmeResponse | ErrorResponse,
)
async def set_floor_get_rooms(
    request: SetFloorRequest, client: ISIMClient = Depends(get_isim_client)
):
    """设置楼层并获取对应的房间列表"""
    try:
        result = await client.get_rooms(request.floor_code)

        response = RoomListResponse.from_data(
            data=result,
            success_message="房间列表获取成功",
            error_message="获取房间列表失败，网络请求多次重试后仍无法连接后勤系统，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        logger.error(f"获取房间列表时发生系统错误: {str(e)}")
        return ErrorResponse(message=f"获取房间列表时发生系统错误：{str(e)}", code=500)


@isim_router.post(
    "/picker/room/set",
    summary="绑定房间",
    response_model=RoomBindingResponse | AuthmeResponse | ErrorResponse,
)
async def bind_room(
    request: SetRoomRequest,
    client: ISIMClient = Depends(get_isim_client),
    asyncsession: AsyncSession = Depends(get_db_session),
):
    """绑定房间并保存到数据库"""
    try:
        # 执行房间绑定
        result = await client.bind_room(
            building_code=request.building_code,
            floor_code=request.floor_code,
            room_code=request.room_code,
        )

        if result:
            # 保存绑定信息到数据库
            async with asyncsession as session:
                try:
                    # 获取用户ID
                    user_id = client.vpn_connection.student_id

                    # 检查是否已存在绑定记录
                    existing_binding = await session.execute(
                        select(ISIMRoomBinding).where(ISIMRoomBinding.userid == user_id)
                    )
                    existing = existing_binding.scalars().first()

                    if existing:
                        # 更新现有记录
                        await session.execute(
                            update(ISIMRoomBinding)
                            .where(ISIMRoomBinding.userid == user_id)
                            .values(
                                building_code=result.building.code,
                                building_name=result.building.name,
                                floor_code=result.floor.code,
                                floor_name=result.floor.name,
                                room_code=result.room.code,
                                room_name=result.room.name,
                                room_id=result.room_id,
                            )
                        )
                        logger.info(
                            f"更新用户房间绑定: {user_id} -> {result.display_text}"
                        )
                    else:
                        # 创建新记录
                        new_binding = ISIMRoomBinding(
                            userid=user_id,
                            building_code=result.building.code,
                            building_name=result.building.name,
                            floor_code=result.floor.code,
                            floor_name=result.floor.name,
                            room_code=result.room.code,
                            room_name=result.room.name,
                            room_id=result.room_id,
                        )
                        session.add(new_binding)
                        logger.info(
                            f"创建用户房间绑定: {user_id} -> {result.display_text}"
                        )

                    await session.commit()

                except Exception as db_error:
                    await session.rollback()
                    logger.error(f"保存房间绑定到数据库失败: {str(db_error)}")
                    # 数据库保存失败不影响绑定结果返回

        response = RoomBindingResponse.from_data(
            data=result,
            success_message="房间绑定成功",
            error_message="房间绑定失败，网络请求多次重试后仍无法连接后勤系统，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        logger.error(f"绑定房间时发生系统错误: {str(e)}")
        return ErrorResponse(message=f"绑定房间时发生系统错误：{str(e)}", code=500)


# ==================== 电费查询API ====================


@isim_router.post(
    "/electricity/info",
    summary="获取电费信息",
    response_model=ElectricityInfoResponse | AuthmeResponse | ErrorResponse,
)
async def get_electricity_info(
    client: ISIMClient = Depends(get_isim_client),
    session: AsyncSession = Depends(get_db_session),
):
    """获取电费余额和用电记录信息"""
    try:
        # 查询用户的房间绑定记录
        from database.isim import ISIMRoomBinding
        from sqlalchemy import select

        result_query = await session.execute(
            select(ISIMRoomBinding).where(ISIMRoomBinding.userid == client.user_id)
        )
        binding_record = result_query.scalars().first()
        # 传递绑定记录给客户端
        result = await client.get_electricity_info(binding_record)

        response = ElectricityInfoResponse.from_data(
            data=result,
            success_message="电费信息获取成功",
            error_message="获取电费信息失败，网络请求多次重试后仍无法连接后勤系统，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        logger.error(f"获取电费信息时发生系统错误: {str(e)}")
        return ErrorResponse(message=f"获取电费信息时发生系统错误：{str(e)}", code=500)


@isim_router.post(
    "/payment/info",
    summary="获取充值信息",
    response_model=PaymentInfoResponse | AuthmeResponse | ErrorResponse,
)
async def get_payment_info(
    client: ISIMClient = Depends(get_isim_client),
    session: AsyncSession = Depends(get_db_session),
):
    """获取电费余额和充值记录信息"""
    try:
        # 查询用户的房间绑定记录
        from database.isim import ISIMRoomBinding
        from sqlalchemy import select

        result_query = await session.execute(
            select(ISIMRoomBinding).where(ISIMRoomBinding.userid == client.user_id)
        )
        binding_record = result_query.scalars().first()
        # 传递绑定记录给客户端
        result = await client.get_payment_info(binding_record)

        response = PaymentInfoResponse.from_data(
            data=result,
            success_message="充值信息获取成功",
            error_message="获取充值信息失败，网络请求多次重试后仍无法连接后勤系统，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        logger.error(f"获取充值信息时发生系统错误: {str(e)}")
        return ErrorResponse(message=f"获取充值信息时发生系统错误：{str(e)}", code=500)


# ==================== 房间绑定状态API ====================


@isim_router.post(
    "/room/binding/status",
    summary="检查用户房间绑定状态",
    response_model=RoomBindingStatusResponse | AuthmeResponse | ErrorResponse,
)
async def check_room_binding_status(
    client: ISIMClient = Depends(get_isim_client),
    asyncsession: AsyncSession = Depends(get_db_session),
):
    """检查用户是否已绑定宿舍房间"""
    try:
        # 获取用户ID
        user_id = client.vpn_connection.student_id

        async with asyncsession as session:
            # 查询数据库中的房间绑定记录
            result = await session.execute(
                select(ISIMRoomBinding).where(ISIMRoomBinding.userid == user_id)
            )
            binding_record = result.scalars().first()

            if binding_record:
                # 用户已绑定房间，构建绑定信息
                binding_info = RoomBindingInfo(
                    building=BuildingInfo(
                        code=binding_record.building_code,
                        name=binding_record.building_name,
                    ),
                    floor=FloorInfo(
                        code=binding_record.floor_code, name=binding_record.floor_name
                    ),
                    room=RoomInfo(
                        code=binding_record.room_code, name=binding_record.room_name
                    ),
                    room_id=binding_record.room_id,
                    display_text=f"{binding_record.building_name}/{binding_record.floor_name}/{binding_record.room_name}",
                )

                status_data = RoomBindingStatusData(
                    is_bound=True, binding_info=binding_info
                )

                logger.info(f"用户 {user_id} 已绑定房间: {binding_info.display_text}")

                return RoomBindingStatusResponse.success(
                    data=status_data, message="用户已绑定宿舍房间"
                )
            else:
                # 用户未绑定房间
                status_data = RoomBindingStatusData(is_bound=False, binding_info=None)

                logger.info(f"用户 {user_id} 未绑定房间")

                return RoomBindingStatusResponse.success(
                    data=status_data, message="用户未绑定宿舍房间"
                )

    except Exception as e:
        logger.error(f"检查房间绑定状态时发生系统错误: {str(e)}")
        return ErrorResponse(
            message=f"检查房间绑定状态时发生系统错误：{str(e)}", code=500
        )
