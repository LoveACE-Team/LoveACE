from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from router.common_model import BaseResponse


class TaskStatusEnum(str, Enum):
    """任务状态枚举"""

    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class CourseInfo(BaseModel):
    """课程信息响应模型"""

    course_id: str = Field("", description="课程ID")
    course_name: str = Field("", description="课程名称")
    teacher_name: str = Field("", description="教师姓名")
    is_evaluated: str = Field("", description="是否已评价")
    evaluation_content: str = Field("", description="评价内容")


# 统一响应数据模型
class EvaluationStatsData(BaseModel):
    """评价统计信息数据模型"""

    total_courses: int = Field(0, description="总课程数")
    pending_courses: int = Field(0, description="待评价课程数")
    success_count: int = Field(0, description="成功评价数")
    fail_count: int = Field(0, description="失败评价数")
    current_index: int = Field(0, description="当前评价索引")
    status: TaskStatusEnum = Field(TaskStatusEnum.IDLE, description="任务状态")
    current_countdown: int = Field(0, description="当前倒计时")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    error_message: str = Field("", description="错误消息")
    course_list: List[CourseInfo] = Field(default_factory=list, description="课程列表")


class CurrentCourseInfoData(BaseModel):
    """当前评价课程信息数据模型"""

    is_evaluating: bool = Field(False, description="是否正在评价")
    course_name: str = Field("", description="课程名称")
    teacher_name: str = Field("", description="教师姓名")
    progress_text: str = Field("", description="进度文本")
    countdown_seconds: int = Field(0, description="倒计时秒数")
    current_index: int = Field(-1, description="当前索引")
    total_pending: int = Field(0, description="总待评价数")


class TaskOperationData(BaseModel):
    """任务操作数据模型"""

    task_status: TaskStatusEnum = Field(TaskStatusEnum.IDLE, description="任务状态")


class InitializeData(BaseModel):
    """初始化数据模型"""

    total_courses: int = Field(0, description="总课程数")
    pending_courses: int = Field(0, description="待评价课程数")
    course_list: List[CourseInfo] = Field(default_factory=list, description="课程列表")


# 统一响应模型
class EvaluationStatsResponse(BaseResponse[EvaluationStatsData]):
    """评价统计信息响应模型"""

    pass


class CurrentCourseInfoResponse(BaseResponse[CurrentCourseInfoData]):
    """当前评价课程信息响应模型"""

    pass


class TaskOperationResponse(BaseResponse[TaskOperationData]):
    """任务操作响应模型"""

    pass


class InitializeResponse(BaseResponse[InitializeData]):
    """初始化响应模型"""

    pass
