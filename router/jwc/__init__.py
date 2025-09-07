from fastapi import Depends
from fastapi.routing import APIRouter
from provider.aufe.jwc import JWCClient
from provider.aufe.jwc.depends import get_jwc_client
from provider.loveac.authme import AuthmeResponse
from router.jwc.model import (
    AcademicInfoResponse,
    TrainingPlanInfoResponse,
    CourseListResponse,
    ExamInfoAPIResponse,
    AllTermsResponse,
    TermScoreAPIResponse,
    FetchTermScoreRequest,
    ScheduleResponse,
    FetchScheduleRequest,
)
from router.common_model import ErrorResponse
from .evaluate_model import (
    EvaluationStatsResponse,
    CurrentCourseInfoResponse,
    TaskOperationResponse,
    InitializeResponse,
    CourseInfo,
    TaskStatusEnum,
    EvaluationStatsData,
    CurrentCourseInfoData,
    TaskOperationData,
    InitializeData,
)
from .evaluate import (
    get_task_manager,
    remove_task_manager,
)
from .plan_completion import router as plan_completion_router
from datetime import datetime
from loguru import logger

jwc_router = APIRouter(prefix="/api/v1/jwc")

# 包含培养方案完成情况路由
jwc_router.include_router(plan_completion_router)

invite_tokens = []



@jwc_router.post(
    "/fetch_academic_info",
    summary="获取学业信息",
    response_model=AcademicInfoResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_academic_info(client: JWCClient = Depends(get_jwc_client)):
    """获取学术信息（课程数量、绩点等）"""
    try:
        result = await client.fetch_academic_info()

        # 检查是否是AuthmeResponse（认证错误）
        if isinstance(result, AuthmeResponse):
            return result

        # 使用新的错误检测机制
        response = AcademicInfoResponse.from_data(
            data=result,
            success_message="学业信息获取成功",
            error_message="获取学业信息失败，网络请求多次重试后仍无法连接教务系统，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        return ErrorResponse(message=f"获取学业信息时发生系统错误：{str(e)}", code=500)


@jwc_router.post(
    "/fetch_education_plan_info",
    summary="获取培养方案信息",
    response_model=TrainingPlanInfoResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_education_plan_info(client: JWCClient = Depends(get_jwc_client)):
    """获取培养方案信息"""
    try:
        result = await client.fetch_training_plan_info()

        # 检查是否是AuthmeResponse（认证错误）
        if isinstance(result, AuthmeResponse):
            return result

        # 使用新的错误检测机制
        response = TrainingPlanInfoResponse.from_data(
            data=result,
            success_message="培养方案信息获取成功",
            error_message="获取培养方案信息失败，网络请求多次重试后仍无法连接教务系统，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        return ErrorResponse(
            message=f"获取培养方案信息时发生系统错误：{str(e)}", code=500
        )


@jwc_router.post(
    "/fetch_evaluation_course_list",
    summary="获取评教课程列表",
    response_model=CourseListResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_evaluation_course_list(client: JWCClient = Depends(get_jwc_client)):
    """获取评教课程列表"""
    try:
        result = await client.fetch_evaluation_course_list()

        # 检查是否是AuthmeResponse（认证错误）
        if isinstance(result, AuthmeResponse):
            return result

        # 对于列表类型，使用特殊的检查逻辑
        if result and len(result) > 0:
            # 检查第一个元素是否是错误数据
            first_course = result[0]
            if (
                hasattr(first_course, "evaluated_people")
                and first_course.evaluated_people == "请求失败"
            ):
                return CourseListResponse.error(
                    message="获取评教课程列表失败，网络请求多次重试后仍无法连接教务系统，请稍后重试或联系管理员",
                    code=500,
                    data=[],
                )
            else:
                return CourseListResponse.success(
                    data=result, message="评教课程列表获取成功"
                )
        else:
            return CourseListResponse.success(data=[], message="暂无需要评教的课程")

    except Exception as e:
        return ErrorResponse(
            message=f"获取评教课程列表时发生系统错误：{str(e)}", code=500
        )


@jwc_router.post(
    "/fetch_exam_info",
    summary="获取考试信息",
    response_model=ExamInfoAPIResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_exam_info(client: JWCClient = Depends(get_jwc_client)):
    """获取考试信息，包括校统考和其他考试"""
    try:
        train_plan_info = await client.fetch_training_plan_info()

        # 检查培养方案信息是否获取失败
        if not train_plan_info or (
            hasattr(train_plan_info, "plan_name")
            and train_plan_info.plan_name == "请求失败，请稍后重试"
        ):
            return ErrorResponse(
                message="无法获取培养方案信息，导致考试信息获取失败。网络请求多次重试后仍无法连接教务系统，请稍后重试或联系管理员",
                code=500,
            )

        # 检查是否是AuthmeResponse
        if isinstance(train_plan_info, AuthmeResponse):
            return train_plan_info

        _term_code = train_plan_info.current_term
        # _term_code -> term_code: "2024-2025春季学期" 转换为 "2024-2025-2-1" "2024-2025秋季学期" 转换为 "2024-2025-1-1"
        # 进行转换
        term_code = f"{_term_code[:4]}-{_term_code[5:9]}-{"1" if _term_code[10] == "秋" else "2"}-1"
        print(f"当前学期代码: {term_code}")
        start_date = datetime.now()
        # termcode 结尾为 1 为秋季学期，考试应在3月之前，2为春季学期，考试应在9月之前
        end_date = datetime(
            year=start_date.year + (1 if term_code.endswith("1") else 0),
            month=3 if term_code.endswith("1") else 9,
            day=30,
        )

        result = await client.fetch_unified_exam_info(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            term_code=term_code,
        )

        # 检查是否是AuthmeResponse（认证错误）
        if isinstance(result, AuthmeResponse):
            return result

        # 使用新的错误检测机制
        response = ExamInfoAPIResponse.from_data(
            data=result,
            success_message="考试信息获取成功",
            error_message="获取考试信息失败，网络请求多次重试后仍无法连接教务系统，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        return ErrorResponse(message=f"获取考试信息时发生系统错误：{str(e)}", code=500)


# ==================== 评价系统API ====================


@jwc_router.post(
    "/evaluation/initialize",
    summary="初始化评价任务",
    response_model=InitializeResponse | AuthmeResponse,
)
async def initialize_evaluation_task(client: JWCClient = Depends(get_jwc_client)):
    """初始化评价任务，获取课程列表"""
    try:
        # 获取用户ID (从JWC客户端获取)
        user_id = getattr(client, "user_id", "unknown")

        # 检查是否已有活跃的任务管理器
        existing_manager = get_task_manager(user_id)
        if existing_manager:
            current_status = existing_manager.get_task_status().status
            if current_status in [
                TaskStatusEnum.RUNNING,
                TaskStatusEnum.PAUSED,
                TaskStatusEnum.INITIALIZING,
            ]:
                return InitializeResponse(
                    code=400,
                    message="您已有一个评价任务在进行中，请先完成或终止当前任务",
                    data=None,
                )
            # 如果任务已完成、失败或终止，移除旧的任务管理器
            elif current_status in [
                TaskStatusEnum.COMPLETED,
                TaskStatusEnum.FAILED,
                TaskStatusEnum.TERMINATED,
            ]:
                remove_task_manager(user_id)

        # 获取或创建任务管理器
        task_manager = get_task_manager(user_id, client)
        if not task_manager:
            return InitializeResponse(code=400, message="创建任务管理器失败", data=None)

        # 执行初始化
        success = await task_manager.initialize()
        stats = task_manager.get_task_status()

        # 转换课程列表格式
        course_list = []
        for course in stats.course_list:
            course_info = CourseInfo(
                course_id=(
                    getattr(course.id, "coure_sequence_number", "") if course.id else ""
                ),
                course_name=course.evaluation_content,
                teacher_name=course.evaluated_people,
                is_evaluated=course.is_evaluated,
                evaluation_content=course.evaluation_content,
            )
            course_list.append(course_info)

        initialize_data = InitializeData(
            total_courses=stats.total_courses,
            pending_courses=stats.pending_courses,
            course_list=course_list,
        )

        return InitializeResponse(
            code=200 if success else 400, message=stats.message, data=initialize_data
        )

    except Exception as e:
        return InitializeResponse(code=500, message=f"初始化失败: {str(e)}", data=None)


@jwc_router.post(
    "/evaluation/start",
    summary="开始评价任务",
    response_model=TaskOperationResponse | AuthmeResponse,
)
async def start_evaluation_task(client: JWCClient = Depends(get_jwc_client)):
    """开始评价任务"""
    try:
        user_id = getattr(client, "user_id", "unknown")

        # 检查是否已有运行中的任务
        existing_manager = get_task_manager(user_id)
        if existing_manager:
            current_status = existing_manager.get_task_status().status
            if current_status.value in [
                TaskStatusEnum.RUNNING.value,
                TaskStatusEnum.PAUSED.value,
            ]:
                task_data = TaskOperationData(
                    task_status=TaskStatusEnum(current_status.value)
                )
                return TaskOperationResponse(
                    code=400,
                    message="您已有一个评价任务在运行中，请先完成或终止当前任务",
                    data=task_data,
                )

        task_manager = get_task_manager(user_id, client)
        if not task_manager:
            task_data = TaskOperationData(task_status=TaskStatusEnum.FAILED)
            return TaskOperationResponse(
                code=400, message="任务管理器不存在，请先初始化", data=task_data
            )

        success = await task_manager.start_evaluation_task()
        stats = task_manager.get_task_status()

        task_data = TaskOperationData(task_status=TaskStatusEnum(stats.status.value))

        return TaskOperationResponse(
            code=200 if success else 400,
            message="任务已启动" if success else "任务启动失败，可能已有任务在运行",
            data=task_data,
        )

    except Exception as e:
        task_data = TaskOperationData(task_status=TaskStatusEnum.FAILED)
        return TaskOperationResponse(
            code=500, message=f"启动任务失败: {str(e)}", data=task_data
        )


@jwc_router.post(
    "/evaluation/terminate",
    summary="终止评价任务",
    response_model=TaskOperationResponse | AuthmeResponse,
)
async def terminate_evaluation_task(client: JWCClient = Depends(get_jwc_client)):
    """终止评价任务"""
    try:
        user_id = getattr(client, "user_id", "unknown")
        task_manager = get_task_manager(user_id)

        if not task_manager:
            task_data = TaskOperationData(task_status=TaskStatusEnum.IDLE)
            return TaskOperationResponse(
                code=400, message="任务管理器不存在", data=task_data
            )

        success = await task_manager.terminate_task()
        stats = task_manager.get_task_status()

        # 移除任务管理器
        remove_task_manager(user_id)

        task_data = TaskOperationData(task_status=TaskStatusEnum(stats.status.value))

        return TaskOperationResponse(
            code=200 if success else 400,
            message="任务已终止" if success else "终止失败",
            data=task_data,
        )

    except Exception as e:
        task_data = TaskOperationData(task_status=TaskStatusEnum.FAILED)
        return TaskOperationResponse(
            code=500, message=f"终止任务失败: {str(e)}", data=task_data
        )


@jwc_router.post(
    "/evaluation/status",
    summary="获取评价任务状态",
    response_model=EvaluationStatsResponse | AuthmeResponse,
)
async def get_evaluation_task_status(client: JWCClient = Depends(get_jwc_client)):
    """获取评价任务状态"""
    try:
        user_id = getattr(client, "user_id", "unknown")
        task_manager = get_task_manager(user_id)

        if not task_manager:
            return EvaluationStatsResponse(code=200, message="无活跃任务", data=None)

        stats = task_manager.get_task_status()

        # 转换课程列表格式
        course_list = []
        for course in stats.course_list:
            course_info = CourseInfo(
                course_id=(
                    getattr(course.id, "coure_sequence_number", "") if course.id else ""
                ),
                course_name=course.evaluation_content,
                teacher_name=course.evaluated_people,
                is_evaluated=course.is_evaluated,
                evaluation_content=course.evaluation_content,
            )
            course_list.append(course_info)

        stats_data = EvaluationStatsData(
            total_courses=stats.total_courses,
            pending_courses=stats.pending_courses,
            success_count=stats.success_count,
            fail_count=stats.fail_count,
            current_index=stats.current_index,
            status=TaskStatusEnum(stats.status.value),
            current_countdown=stats.current_countdown,
            start_time=stats.start_time,
            end_time=stats.end_time,
            error_message=stats.error_message,
            course_list=course_list,
        )

        return EvaluationStatsResponse(code=200, message=stats.message, data=stats_data)

    except Exception as e:
        return EvaluationStatsResponse(
            code=500, message=f"获取状态失败: {str(e)}", data=None
        )


@jwc_router.post(
    "/evaluation/current",
    summary="获取当前评价课程信息",
    response_model=CurrentCourseInfoResponse | AuthmeResponse,
)
async def get_current_course_info(client: JWCClient = Depends(get_jwc_client)):
    """获取当前评价课程信息"""
    try:
        user_id = getattr(client, "user_id", "unknown")
        task_manager = get_task_manager(user_id)

        if not task_manager:
            return CurrentCourseInfoResponse(code=200, message="无活跃任务", data=None)

        current_info = task_manager.get_current_course_info()

        course_info_data = CurrentCourseInfoData(
            is_evaluating=current_info.is_evaluating,
            course_name=current_info.course_name,
            teacher_name=current_info.teacher_name,
            progress_text=current_info.progress_text,
            countdown_seconds=current_info.countdown_seconds,
            current_index=current_info.current_index,
            total_pending=current_info.total_pending,
        )

        return CurrentCourseInfoResponse(
            code=200, message="获取成功", data=course_info_data
        )

    except Exception as e:
        return CurrentCourseInfoResponse(
            code=500, message=f"获取信息失败: {str(e)}", data=None
        )


# ==================== 学期和成绩相关API ====================


@jwc_router.post(
    "/fetch_all_terms",
    summary="获取所有学期信息",
    response_model=AllTermsResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_all_terms(client: JWCClient = Depends(get_jwc_client)):
    """获取所有可查询的学期信息"""
    try:
        result = await client.fetch_all_terms()

        # 检查结果
        if result and len(result) > 0:
            return AllTermsResponse.success(data=result, message="学期信息获取成功")
        else:
            return AllTermsResponse.error(
                message="获取学期信息失败，网络请求多次重试后仍无法连接教务系统，请稍后重试或联系管理员",
                code=500,
                data={},
            )

    except Exception as e:
        return ErrorResponse(message=f"获取学期信息时发生系统错误：{str(e)}", code=500)


@jwc_router.post(
    "/fetch_term_score",
    summary="获取指定学期成绩",
    response_model=TermScoreAPIResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_term_score(
    request: FetchTermScoreRequest,
    client: JWCClient = Depends(get_jwc_client),
):
    """
    获取指定学期的成绩信息
    """
    try:
        raw_result = await client.fetch_term_score(
            term_id=request.term_id,
            course_code=request.course_code,
            course_name=request.course_name,
            page_num=request.page_num,
            page_size=request.page_size,
        )

        if not raw_result:
            return TermScoreAPIResponse.error(
                message="获取成绩信息失败，网络请求多次重试后仍无法连接教务系统，请稍后重试或联系管理员",
                code=500,
                data=None,
            )

        try:
            # 解析原始数据为结构化数据
            from provider.aufe.jwc.model import TermScoreResponse, ScoreRecord

            list_data = raw_result.get("list", {})
            page_context = list_data.get("pageContext", {})
            records_raw = list_data.get("records", [])

            # 转换记录格式
            score_records = []
            for record in records_raw:
                if len(record) >= 13:  # 确保数据完整
                    score_record = ScoreRecord(
                        sequence=record[0] if record[0] else 0,
                        term_id=record[1] if record[1] else "",
                        course_code=record[2] if record[2] else "",
                        course_class=record[3] if record[3] else "",
                        course_name_cn=record[4] if record[4] else "",
                        course_name_en=record[5] if record[5] else "",
                        credits=record[6] if record[6] else "",
                        hours=record[7] if record[7] else 0,
                        course_type=record[8] if record[8] else "",
                        exam_type=record[9] if record[9] else "",
                        score=record[10] if record[10] else "",
                        retake_score=(
                            record[11] if len(record) > 11 and record[11] else None
                        ),
                        makeup_score=(
                            record[12] if len(record) > 12 and record[12] else None
                        ),
                    )
                    score_records.append(score_record)

            result = TermScoreResponse(
                page_size=list_data.get("pageSize", 50),
                page_num=list_data.get("pageNum", 1),
                total_count=page_context.get("totalCount", 0),
                records=score_records,
            )

            return TermScoreAPIResponse(
                code=200,
                message="success",
                data=result,
            )

        except Exception as parse_error:
            return TermScoreAPIResponse.error(
                message=f"解析成绩数据失败：{str(parse_error)}", code=500, data=None
            )

    except Exception as e:
        logger.error(f"获取学期成绩失败: {str(e)}")
        return ErrorResponse(code=1, message=f"获取学期成绩失败: {str(e)}")


@jwc_router.post(
    "/fetch_course_schedule",
    summary="获取课表信息",
    response_model=ScheduleResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_course_schedule(
    request: FetchScheduleRequest,
    client: JWCClient = Depends(get_jwc_client)
):
    """
    获取聚合的课表信息，包含：
    - 课程基本信息（课程名、教师、学分等）
    - 上课时间和地点信息
    - 时间段详情
    - 学期信息
    
    特殊处理：
    - 自动过滤无用字段
    - 标记没有具体时间安排的课程
    - 清理教师姓名中的特殊字符
    """
    try:
        logger.info(f"获取课表请求: plan_code={request.plan_code}")
        
        # 检查环境和Cookie有效性
        is_valid = await client.validate_environment_and_cookie()
        if not is_valid:
            return AuthmeResponse(
                code=401,
                message="Cookie已失效或不在VPN/校园网环境，请重新登录",
            )

        # 获取处理后的课表数据
        schedule_data = await client.get_processed_schedule(request.plan_code)
        
        if not schedule_data:
            return ErrorResponse(
                code=1,
                message="获取课表信息失败，请稍后重试"
            )

        return ScheduleResponse(
            code=0,
            message="success",
            data=schedule_data,
        )
    except Exception as e:
        logger.error(f"获取课表信息失败: {str(e)}")
        return ErrorResponse(code=1, message=f"获取课表信息失败: {str(e)}")
