from typing import List, Optional
from pydantic import BaseModel, Field
from provider.aufe.isim.model import (
    BuildingInfo,
    FloorInfo, 
    RoomInfo,
    RoomBindingInfo,
    ElectricityInfo,
    PaymentInfo
)
from router.common_model import BaseResponse


# ==================== 请求模型 ====================

class AuthmeRequest(BaseModel):
    """认证请求基类"""
    authme_token: str = Field(..., description="认证令牌")


class SetBuildingRequest(AuthmeRequest):
    """设置楼栋请求"""
    building_code: str = Field(..., description="楼栋代码")


class SetFloorRequest(AuthmeRequest):
    """设置楼层请求"""
    floor_code: str = Field(..., description="楼层代码")


class SetRoomRequest(AuthmeRequest):
    """设置房间请求"""
    building_code: str = Field(..., description="楼栋代码")
    floor_code: str = Field(..., description="楼层代码") 
    room_code: str = Field(..., description="房间代码")


# ==================== 响应模型 ====================

class BuildingListResponse(BaseResponse):
    """楼栋列表响应"""
    data: Optional[List[BuildingInfo]] = Field(default=None, description="楼栋信息列表")
    
    @classmethod
    def from_data(cls, data: List[BuildingInfo], success_message: str, error_message: str):
        """根据数据创建响应"""
        if data and len(data) > 0:
            # 检查是否是错误数据（第一个楼栋名称为"请求失败"）
            if data[0].name == "请求失败":
                return cls.error(message=error_message, code=500, data=None)
            else:
                return cls.success(data=data, message=success_message)
        else:
            return cls.error(message=error_message, code=500, data=None)


class FloorListResponse(BaseResponse):
    """楼层列表响应"""
    data: Optional[List[FloorInfo]] = Field(default=None, description="楼层信息列表")
    
    @classmethod
    def from_data(cls, data: List[FloorInfo], success_message: str, error_message: str):
        """根据数据创建响应"""
        if data and len(data) > 0:
            return cls.success(data=data, message=success_message)
        else:
            return cls.error(message=error_message, code=500, data=None)


class RoomListResponse(BaseResponse):
    """房间列表响应"""
    data: Optional[List[RoomInfo]] = Field(default=None, description="房间信息列表")
    
    @classmethod
    def from_data(cls, data: List[RoomInfo], success_message: str, error_message: str):
        """根据数据创建响应"""
        if data and len(data) > 0:
            return cls.success(data=data, message=success_message)
        else:
            return cls.error(message=error_message, code=500, data=None)


class RoomBindingResponse(BaseResponse):
    """房间绑定响应"""
    data: Optional[RoomBindingInfo] = Field(default=None, description="房间绑定信息")
    
    @classmethod
    def from_data(cls, data: Optional[RoomBindingInfo], success_message: str, error_message: str):
        """根据数据创建响应"""
        if data and hasattr(data, 'building') and data.building.name != "请求失败":
            return cls.success(data=data, message=success_message)
        else:
            return cls.error(message=error_message, code=500, data=None)


class ElectricityInfoResponse(BaseResponse):
    """电费信息响应"""
    data: Optional[ElectricityInfo] = Field(default=None, description="电费信息")
    
    @classmethod
    def from_data(cls, data: ElectricityInfo, success_message: str, error_message: str):
        """根据数据创建响应"""
        # 检查是否是错误数据
        if data.balance.remaining_purchased >= 0 and data.balance.remaining_subsidy >= 0:
            return cls.success(data=data, message=success_message)
        elif data.balance.remaining_purchased == -2.0 and data.balance.remaining_subsidy == -2.0:
            # 未绑定房间的特定错误
            return cls.error(message="请先绑定宿舍房间后再查询电费信息", code=400, data=None)
        else:
            return cls.error(message=error_message, code=500, data=None)


class PaymentInfoResponse(BaseResponse):
    """充值信息响应"""
    data: Optional[PaymentInfo] = Field(default=None, description="充值信息")
    
    @classmethod
    def from_data(cls, data: PaymentInfo, success_message: str, error_message: str):
        """根据数据创建响应"""
        # 检查是否是错误数据
        if data.balance.remaining_purchased >= 0 and data.balance.remaining_subsidy >= 0:
            return cls.success(data=data, message=success_message)
        elif data.balance.remaining_purchased == -2.0 and data.balance.remaining_subsidy == -2.0:
            # 未绑定房间的特定错误
            return cls.error(message="请先绑定宿舍房间后再查询充值信息", code=400, data=None)
        else:
            return cls.error(message=error_message, code=500, data=None)


# ==================== 房间绑定状态相关模型 ====================

class RoomBindingStatusData(BaseModel):
    """房间绑定状态数据"""
    is_bound: bool = Field(..., description="是否已绑定房间")
    binding_info: Optional[RoomBindingInfo] = Field(default=None, description="绑定信息（如果已绑定）")


class RoomBindingStatusResponse(BaseResponse):
    """房间绑定状态响应"""
    data: Optional[RoomBindingStatusData] = Field(default=None, description="绑定状态信息")
