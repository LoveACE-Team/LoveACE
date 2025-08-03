from typing import Generic, Optional, TypeVar, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """通用响应模型基类"""

    code: int = Field(200, description="状态码")
    message: str = Field("成功", description="提示信息")
    data: Optional[T] = Field(None, description="响应数据")

    @classmethod
    def success(cls, data: T, message: str = "获取成功") -> "BaseResponse[T]":
        """创建成功响应"""
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(
        cls, message: str = "请求失败", code: int = 500, data: Optional[T] = None
    ) -> "BaseResponse[T]":
        """创建错误响应"""
        return cls(code=code, message=message, data=data)

    @classmethod
    def from_data(
        cls,
        data: Any,
        success_message: str = "获取成功",
        error_message: str = "网络请求失败，已进行多次重试",
    ) -> "BaseResponse[T]":
        """
        根据数据自动判断是否为错误模型并生成相应响应

        Args:
            data: 要检查的数据
            success_message: 成功时的消息
            error_message: 失败时的消息

        Returns:
            BaseResponse: 相应的响应模型
        """
        if cls._is_error_data(data):
            return cls.error(message=error_message, code=500, data=data)
        else:
            return cls.success(data=data, message=success_message)

    @staticmethod
    def _is_error_data(data: Any) -> bool:
        """
        检测数据是否为错误模型

        Args:
            data: 要检查的数据

        Returns:
            bool: 如果是错误数据返回True
        """
        if data is None:
            return True

        # 检查是否有错误指示符
        if hasattr(data, "total_score") and data.total_score == -1.0:
            return True
        if hasattr(data, "completed_courses") and data.completed_courses == -1:
            return True
        if hasattr(data, "gpa") and data.gpa == -1.0:
            return True
        if hasattr(data, "plan_name") and data.plan_name == "请求失败，请稍后重试":
            return True
        if hasattr(data, "code") and data.code == -1:
            return True
        if hasattr(data, "total_count") and data.total_count == -1:
            return True
        if hasattr(data, "result") and data.result == "failed":
            return True
        if (
            hasattr(data, "can_select")
            and hasattr(data, "start_time")
            and data.start_time == "请求失败"
        ):
            return True

        # 检查列表类型的错误数据
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            if hasattr(first_item, "id") and first_item.id == "error":
                return True
            if hasattr(first_item, "type_name") and first_item.type_name == "请求失败":
                return True

        return False


class ErrorResponse(BaseResponse[None]):
    """专用错误响应模型"""

    def __init__(self, message: str = "请求失败，请稍后重试", code: int = 500):
        super().__init__(code=code, message=message, data=None)
