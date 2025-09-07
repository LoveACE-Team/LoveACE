from fastapi import APIRouter, Depends
from typing import Optional
from loguru import logger

from provider.aufe.jwc import JWCClient
from provider.aufe.jwc.depends import get_jwc_client
from provider.loveac.authme import AuthmeResponse
from provider.aufe.jwc.plan_completion_model import (
    PlanCompletionInfo,
    ErrorPlanCompletionInfo,
)
from provider.aufe.jwc.semester_week_model import (
    SemesterWeekInfo,
    ErrorSemesterWeekInfo,
)
from router.common_model import BaseResponse, ErrorResponse


router = APIRouter(prefix="/plan-completion", tags=["培养方案完成情况"])


class PlanCompletionInfoResponse(BaseResponse):
    """培养方案完成情况响应模型"""
    data: Optional[PlanCompletionInfo] = None
    
    @classmethod
    def from_data(
        cls,
        data: PlanCompletionInfo,
        success_message: str = "success",
        error_message: str = "请求失败",
    ) -> "PlanCompletionInfoResponse":
        """根据数据创建响应"""
        if isinstance(data, ErrorPlanCompletionInfo) or data.total_courses == -1:
            return cls(code=-1, message=error_message, data=None)
        return cls(code=0, message=success_message, data=data)


@router.post(
    "/fetch_plan_completion_info",
    summary="获取培养方案完成情况",
    response_model=PlanCompletionInfoResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_plan_completion_info(client: JWCClient = Depends(get_jwc_client)):
    """
    获取培养方案完成情况信息
    
    返回数据包括：
    - 培养方案基本信息（名称、专业、年级）
    - 各分类的完成情况（通识通修、专业课等）
    - 每门课程的详细状态（已通过、未通过、未修读）
    - 统计信息（总课程数、通过数等）
    """
    try:
        result = await client.fetch_plan_completion_info()
        
        # 检查是否是AuthmeResponse（认证错误）
        if isinstance(result, AuthmeResponse):
            return result

        # 使用新的错误检测机制
        response = PlanCompletionInfoResponse.from_data(
            data=result,
            success_message="培养方案完成情况获取成功",
            error_message="获取培养方案完成情况失败，网络请求多次重试后仍无法连接教务系统，请稍后重试或联系管理员",
        )
        return response
        
    except Exception as e:
        logger.error(f"获取培养方案完成情况异常: {str(e)}")
        return ErrorResponse(message=f"获取培养方案完成情况时发生系统错误：{str(e)}", code=500)


@router.post(
    "/fetch_plan_completion_statistics",
    summary="获取培养方案完成统计",
    response_model=BaseResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_plan_completion_statistics(client: JWCClient = Depends(get_jwc_client)):
    """
    获取培养方案完成情况统计信息
    
    返回简化的统计数据，包括：
    - 总分类数
    - 总课程数  
    - 已通过课程数
    - 未通过课程数
    - 未修读课程数
    - 完成率
    """
    try:
        result = await client.fetch_plan_completion_info()
        
        # 检查是否是AuthmeResponse（认证错误）
        if isinstance(result, AuthmeResponse):
            return result
        
        # 检查是否是错误结果
        if isinstance(result, ErrorPlanCompletionInfo) or result.total_courses == -1:
            return BaseResponse(
                code=-1,
                message="获取培养方案统计信息失败，网络请求多次重试后仍无法连接教务系统，请稍后重试或联系管理员",
                data=None
            )
        
        # 构建统计数据
        statistics = {
            "plan_name": result.plan_name,
            "major": result.major,
            "grade": result.grade,
            "total_categories": result.total_categories,
            "total_courses": result.total_courses,
            "passed_courses": result.passed_courses,
            "failed_courses": result.failed_courses,
            "unread_courses": result.unread_courses,
            "completion_rate": round(
                result.passed_courses / result.total_courses * 100, 2
            ) if result.total_courses > 0 else 0.0
        }
        
        return BaseResponse(
            code=0,
            message="培养方案统计信息获取成功",
            data=statistics
        )
        
    except Exception as e:
        logger.error(f"获取培养方案统计信息异常: {str(e)}")
        return ErrorResponse(message=f"获取培养方案统计信息时发生系统错误：{str(e)}", code=500)


class SemesterWeekInfoResponse(BaseResponse):
    """学期周数信息响应模型"""
    data: Optional[SemesterWeekInfo] = None
    
    @classmethod
    def from_data(
        cls,
        data: SemesterWeekInfo,
        success_message: str = "success",
        error_message: str = "请求失败",
    ) -> "SemesterWeekInfoResponse":
        """根据数据创建响应"""
        if isinstance(data, ErrorSemesterWeekInfo) or data.week_number == -1:
            return cls(code=-1, message=error_message, data=None)
        return cls(code=0, message=success_message, data=data)


@router.post("/fetch_semester_week_info", response_model=SemesterWeekInfoResponse, summary="获取学期周数信息")
async def fetch_semester_week_info(
    jwc_client: JWCClient = Depends(get_jwc_client)
) -> SemesterWeekInfoResponse:
    """
    获取当前学期周数信息
    
    需要认证，返回当前学期、周数、是否结束等信息
    """
    try:
        logger.info("开始获取学期周数信息")
        
        result = await jwc_client.fetch_semester_week_info()
        
        if isinstance(result, ErrorSemesterWeekInfo) or result.week_number == -1:
            logger.warning("获取学期周数信息失败")
            return SemesterWeekInfoResponse.from_data(
                result, 
                error_message="获取学期周数信息失败，请稍后重试"
            )
        
        logger.info(f"学期周数信息获取成功: {result.academic_year} {result.semester} 第{result.week_number}周")
        return SemesterWeekInfoResponse.from_data(
            result, 
            success_message="学期周数信息获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取学期周数信息异常: {str(e)}")
        return SemesterWeekInfoResponse(
            code=500,
            message=f"获取学期周数信息时发生系统错误：{str(e)}",
            data=None
        )
