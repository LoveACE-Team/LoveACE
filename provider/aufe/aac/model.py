from typing import List, Optional, Any
from pydantic import BaseModel, Field


class LoveACScoreInfo(BaseModel):
    """爱安财总分信息"""

    total_score: float = Field(0.0, alias="TotalScore")
    is_type_adopt: bool = Field(False, alias="IsTypeAdopt")
    type_adopt_result: str = Field("", alias="TypeAdoptResult")


class LoveACScoreItem(BaseModel):
    """爱安财分数明细条目"""

    id: str = Field("", alias="ID")
    title: str = Field("", alias="Title")
    type_name: str = Field("", alias="TypeName")
    user_no: str = Field("", alias="UserNo")
    score: float = Field(0.0, alias="Score")
    add_time: str = Field("", alias="AddTime")


class LoveACScoreCategory(BaseModel):
    """爱安财分数类别"""

    id: str = Field("", alias="ID")
    show_num: int = Field(0, alias="ShowNum")
    type_name: str = Field("", alias="TypeName")
    total_score: float = Field(0.0, alias="TotalScore")
    children: List[LoveACScoreItem] = Field([], alias="children")


class LoveACBaseResponse(BaseModel):
    """爱安财系统响应基础模型"""

    code: int = 0
    msg: str = ""
    data: Any = None


class LoveACScoreInfoResponse(LoveACBaseResponse):
    """爱安财总分响应"""

    data: Optional[LoveACScoreInfo] = None


class LoveACScoreListResponse(LoveACBaseResponse):
    """爱安财分数列表响应"""

    data: Optional[List[LoveACScoreCategory]] = None


class SimpleResponse(BaseModel):
    """简单响应类，用于解析基本的JSON结构"""

    code: int = 0
    msg: str = ""
    data: Any = None


class ErrorLoveACScoreInfo(LoveACScoreInfo):
    """错误的爱安财总分信息模型，用于重试失败时返回"""

    total_score: float = Field(-1.0, alias="TotalScore")
    is_type_adopt: bool = Field(False, alias="IsTypeAdopt")
    type_adopt_result: str = Field("请求失败，请稍后重试", alias="TypeAdoptResult")


class ErrorLoveACScoreCategory(BaseModel):
    """错误的爱安财分数类别模型"""

    id: str = Field("error", alias="ID")
    show_num: int = Field(-1, alias="ShowNum")
    type_name: str = Field("请求失败", alias="TypeName")
    total_score: float = Field(-1.0, alias="TotalScore")
    children: List[LoveACScoreItem] = Field([], alias="children")


class ErrorLoveACBaseResponse(BaseModel):
    """错误的爱安财系统响应基础模型"""

    code: int = -1
    msg: str = "网络请求失败，已进行多次重试"
    data: Any = None


class ErrorLoveACScoreInfoResponse(ErrorLoveACBaseResponse):
    """错误的爱安财总分响应"""

    data: Optional[ErrorLoveACScoreInfo] = ErrorLoveACScoreInfo(
        TotalScore=-1.0, IsTypeAdopt=False, TypeAdoptResult="请求失败，请稍后重试"
    )


class ErrorLoveACScoreListResponse(LoveACScoreListResponse):
    """错误的爱安财分数列表响应"""

    code: int = -1
    msg: str = "网络请求失败，已进行多次重试"
    data: Optional[List[ErrorLoveACScoreCategory]] = [
        ErrorLoveACScoreCategory(
            ID="error", ShowNum=-1, TypeName="请求失败", TotalScore=-1.0, children=[]
        )
    ]
