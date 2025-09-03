from typing import List, Optional
from pydantic import BaseModel, Field


# ==================== 基础数据模型 ====================

class BuildingInfo(BaseModel):
    """楼栋信息"""
    code: str = Field(..., description="楼栋代码")
    name: str = Field(..., description="楼栋名称")


class FloorInfo(BaseModel):
    """楼层信息"""
    code: str = Field(..., description="楼层代码")
    name: str = Field(..., description="楼层名称")


class RoomInfo(BaseModel):
    """房间信息"""
    code: str = Field(..., description="房间代码")
    name: str = Field(..., description="房间名称")


class RoomBindingInfo(BaseModel):
    """房间绑定信息"""
    building: BuildingInfo
    floor: FloorInfo
    room: RoomInfo
    room_id: str = Field(..., description="完整房间ID")
    display_text: str = Field(..., description="显示文本，如：北苑11号学生公寓/11-6层/11-627")


# ==================== 电费相关模型 ====================

class ElectricityBalance(BaseModel):
    """电费余额信息"""
    remaining_purchased: float = Field(..., description="剩余购电（度）")
    remaining_subsidy: float = Field(..., description="剩余补助（度）")


class ElectricityUsageRecord(BaseModel):
    """用电记录"""
    record_time: str = Field(..., description="记录时间，如：2025-08-29 00:04:58")
    usage_amount: float = Field(..., description="用电量（度）")
    meter_name: str = Field(..., description="电表名称，如：1-101 或 1-101空调")


class ElectricityInfo(BaseModel):
    """电费信息汇总"""
    balance: ElectricityBalance
    usage_records: List[ElectricityUsageRecord]


# ==================== 充值相关模型 ====================

class PaymentRecord(BaseModel):
    """充值记录"""
    payment_time: str = Field(..., description="充值时间，如：2025-02-21 11:30:08")
    amount: float = Field(..., description="充值金额（元）")
    payment_type: str = Field(..., description="充值类型，如：下发补助、一卡通充值")


class PaymentInfo(BaseModel):
    """充值信息汇总"""
    balance: ElectricityBalance
    payment_records: List[PaymentRecord]


# ==================== API响应模型 ====================

class ISIMResponse(BaseModel):
    """ISIM系统基础响应模型"""
    code: int = Field(..., description="响应代码，0表示成功")
    message: str = Field(..., description="响应消息")
    
    @classmethod
    def success(cls, message: str = "操作成功", **kwargs):
        """创建成功响应"""
        return cls(code=0, message=message, **kwargs)
    
    @classmethod
    def error(cls, message: str, code: int = 1, **kwargs):
        """创建错误响应"""
        return cls(code=code, message=message, **kwargs)


class BuildingListResponse(ISIMResponse):
    """楼栋列表响应"""
    data: List[BuildingInfo] = Field(default_factory=list)


class FloorListResponse(ISIMResponse):
    """楼层列表响应"""
    data: List[FloorInfo] = Field(default_factory=list)


class RoomListResponse(ISIMResponse):
    """房间列表响应"""
    data: List[RoomInfo] = Field(default_factory=list)


class RoomBindingResponse(ISIMResponse):
    """房间绑定响应"""
    data: Optional[RoomBindingInfo] = None


class ElectricityInfoResponse(ISIMResponse):
    """电费信息响应"""
    data: Optional[ElectricityInfo] = None


class PaymentInfoResponse(ISIMResponse):
    """充值信息响应"""
    data: Optional[PaymentInfo] = None


# ==================== 请求模型 ====================

class SetBuildingRequest(BaseModel):
    """设置楼栋请求"""
    building_code: str = Field(..., description="楼栋代码")


class SetFloorRequest(BaseModel):
    """设置楼层请求"""
    floor_code: str = Field(..., description="楼层代码")


class SetRoomRequest(BaseModel):
    """设置房间请求"""
    building_code: str = Field(..., description="楼栋代码")
    floor_code: str = Field(..., description="楼层代码")
    room_code: str = Field(..., description="房间代码")


# ==================== 错误模型 ====================

class ErrorRoomBinding(BaseModel):
    """错误房间绑定信息"""
    building: BuildingInfo = BuildingInfo(code="", name="请求失败")
    floor: FloorInfo = FloorInfo(code="", name="")
    room: RoomInfo = RoomInfo(code="", name="")
    room_id: str = ""
    display_text: str = "获取房间信息失败，请稍后重试"


class ErrorElectricityInfo(BaseModel):
    """错误电费信息"""
    balance: ElectricityBalance = ElectricityBalance(remaining_purchased=-1.0, remaining_subsidy=-1.0)
    usage_records: List[ElectricityUsageRecord] = []


class ErrorPaymentInfo(BaseModel):
    """错误充值信息"""
    balance: ElectricityBalance = ElectricityBalance(remaining_purchased=-1.0, remaining_subsidy=-1.0)
    payment_records: List[PaymentRecord] = []


class UnboundRoomElectricityInfo(BaseModel):
    """未绑定房间的电费信息错误"""
    balance: ElectricityBalance = ElectricityBalance(remaining_purchased=-2.0, remaining_subsidy=-2.0)
    usage_records: List[ElectricityUsageRecord] = []


class UnboundRoomPaymentInfo(BaseModel):
    """未绑定房间的充值信息错误"""
    balance: ElectricityBalance = ElectricityBalance(remaining_purchased=-2.0, remaining_subsidy=-2.0)
    payment_records: List[PaymentRecord] = []
