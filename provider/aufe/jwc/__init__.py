import re
import json
import asyncio
from typing import List, Optional, Dict
from loguru import logger
from provider.aufe.jwc.model import (
    AcademicDataItem,
    AcademicInfo,
    TrainingPlanResponseWrapper,
    TrainingPlanInfo,
    CourseSelectionStatusDirectResponse,
    CourseSelectionStatus,
    Course,
    CourseListResponse,
    EvaluationResponse,
    EvaluationRequestParam,
    ExamScheduleItem,
    OtherExamResponse,
    UnifiedExamInfo,
    ExamInfoResponse,
    ErrorAcademicInfo,
    ErrorTrainingPlanInfo,
)
from provider.aufe.jwc.plan_completion_model import (
    PlanCompletionInfo,
    PlanCompletionCategory,
    PlanCompletionCourse,
    ErrorPlanCompletionInfo,
)
from provider.aufe.jwc.semester_week_model import (
    SemesterWeekInfo,
    ErrorSemesterWeekInfo,
)
from provider.aufe.client import (
    AUFEConnection,
    aufe_config_global,
    activity_tracker,
    retry_async,
    AUFEConnectionError,
    AUFEParseError,
    RetryConfig
)
from bs4 import BeautifulSoup


class JWCConfig:
    """教务系统配置常量"""
    DEFAULT_BASE_URL = "http://jwcxk2-aufe-edu-cn.vpn2.aufe.edu.cn:8118/"
    
    # 各类请求的相对路径
    ENDPOINTS = {
        "academic_info": "/student/integratedQuery/scoreQuery/index",
        "training_plan": "/student/integratedQuery/planCompletion/index",
        "plan_completion": "/student/integratedQuery/planCompletion/index",
        "course_selection_status": "/main/checkSelectCourseStatus?sf_request_type=ajax",
        "evaluation_token": "/student/teachingEvaluation/evaluation/index", 
        "course_list": "/student/teachingEvaluation/teachingEvaluation/search?sf_request_type=ajax",
        "exam_terms": "/student/integratedQuery/scoreQuery/courseScore/getTermList?sf_request_type=ajax",
        "student_schedule": "/student/courseSchedule/thisSemesterCurriculum/index",
        "course_schedule": "/student/courseSchedule/courseSchedule/ajaxStudentSchedule/curr/callback"
    }
    
    # 默认分页参数
    DEFAULT_PAGE_SIZE = 50
    MAX_REDIRECTS = 10


class JWCClient:
    """教务系统客户端"""

    def __init__(
        self,
        vpn_connection: AUFEConnection,
        base_url: str = JWCConfig.DEFAULT_BASE_URL,
        retry_config: Optional[RetryConfig] = None
    ):
        """
        初始化教务系统客户端

        Args:
            vpn_connection: VPN连接实例
            base_url: 教务系统基础URL
            retry_config: 重试配置
        """
        self.vpn_connection = vpn_connection
        self.base_url = base_url.rstrip("/")
        self.retry_config = retry_config or RetryConfig()
        
        # 保存课程列表响应结果，以便在后续操作中使用
        self.course_list_response: Optional[CourseListResponse] = None
        
        logger.info(f"教务系统客户端初始化: base_url={self.base_url}")
        
    def _get_default_headers(self) -> dict:
        """获取默认请求头"""
        return aufe_config_global.DEFAULT_HEADERS.copy()
        
    def _get_endpoint_url(self, endpoint: str) -> str:
        """获取端点完整URL"""
        path = JWCConfig.ENDPOINTS.get(endpoint, endpoint)
        return f"{self.base_url}{path}"

    @activity_tracker
    @retry_async()
    async def validate_environment_and_cookie(self) -> bool:
        """
        验证环境（VPN或校园网）和Cookie有效性

        Returns:
            bool: Cookie是否有效
            
        Raises:
            AUFEConnectionError: 连接失败
        """
        try:
            # 检查是否能访问教务系统首页
            headers = self._get_default_headers()
            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/", headers=headers, follow_redirects=True
            )
            is_valid = response.status_code == 200

            logger.info(
                f"环境和Cookie验证结果: {'有效' if is_valid else '无效'} (HTTP状态码: {response.status_code})"
            )

            # 如果Cookie无效或不在VPN/校园网环境，返回false以提示用户重新登录
            if not is_valid:
                logger.error("Cookie无效或不在VPN/校园网环境，需要重新登录")
                raise AUFEConnectionError(f"Cookie验证失败，状态码: {response.status_code}")

            return is_valid
            
        except AUFEConnectionError:
            raise
        except Exception as e:
            logger.error(f"验证环境和Cookie异常: {str(e)}")
            raise AUFEConnectionError(f"环境验证失败: {str(e)}") from e

    @activity_tracker
    @retry_async()
    async def check_network_connection(self) -> bool:
        """
        获取网络连接状态

        Returns:
            bool: 网络是否可用
            
        Raises:
            AUFEConnectionError: 连接失败
        """
        try:
            response = await self.vpn_connection.requester().get(self.base_url)
            is_success = response.status_code in [200, 302]

            logger.info(
                f"网络连接检查结果: {is_success} (HTTP状态码: {response.status_code})"
            )
            
            if not is_success:
                raise AUFEConnectionError(f"网络连接失败，状态码: {response.status_code}")
                
            return is_success
            
        except AUFEConnectionError:
            raise
        except Exception as e:
            logger.error(f"网络连接检查异常: {str(e)}")
            raise AUFEConnectionError(f"网络检查失败: {str(e)}") from e

    @activity_tracker
    @retry_async()
    async def fetch_academic_info(self) -> AcademicInfo:
        """
        获取学术信息（课程数量、绩点等），使用重试机制

        Returns:
            AcademicInfo: 学术信息，失败时返回错误模型
        """
        def _create_error_info() -> ErrorAcademicInfo:
            """创建错误学术信息"""
            return ErrorAcademicInfo(count=-1, countNotPass=-1, gpa=-1.0)
            
        try:
            logger.info("开始获取学术信息")

            headers = self._get_default_headers()
            data = {"flag": ""}

            # 由于这个API返回的是数组格式，需要特殊处理
            response = await self.vpn_connection.requester().post(
                f"{self.base_url}/main/academicInfo?sf_request_type=ajax",
                headers=headers,
                data=data,
                follow_redirects=True,
            )

            if response.status_code != 200:
                raise AUFEConnectionError(f"获取学术信息失败，状态码: {response.status_code}")

            try:
                json_data = response.json()
                # 按数组格式解析响应
                academic_data_items = [
                    AcademicDataItem.parse_obj(item) for item in json_data
                ]

                if not academic_data_items:
                    raise AUFEParseError("未获取到学术信息数据")
                    
                item = academic_data_items[0]
                logger.info(
                    f"学术信息获取成功: 课程数={item.completed_courses}, 绩点={item.gpa}"
                )

                # 转换为AcademicInfo格式返回，保持兼容性
                return AcademicInfo(
                    count=item.completed_courses,
                    countNotPass=item.failed_courses,
                    gpa=item.gpa,
                )
                
            except Exception as e:
                logger.error(f"解析学术信息异常: {str(e)}")
                raise AUFEParseError(f"学术信息解析失败: {str(e)}") from e
                
        except (AUFEConnectionError, AUFEParseError) as e:
            logger.error(f"获取学术信息失败: {str(e)}")
            return _create_error_info()
        except Exception as e:
            logger.error(f"获取学术信息异常: {str(e)}")
            return _create_error_info()

    @activity_tracker
    async def fetch_training_plan_info(self) -> TrainingPlanInfo:
        """
        获取培养方案信息，使用重试机制

        Returns:
            TrainingPlanInfo: 培养方案信息，失败时返回错误模型
        """
        def _create_error_plan_info(error_msg: str = "请求失败，请稍后重试") -> ErrorTrainingPlanInfo:
            """创建错误培养方案信息"""
            return ErrorTrainingPlanInfo(
                pyfa=error_msg,
                term="",
                courseCount=-1,
                major="请求失败",
                grade="",
            )
            
        def _convert_term_format(zxjxjhh: str) -> str:
            """
            转换学期格式
            xxxx-yyyy-1-1 -> xxxx-yyyy秋季学期
            xxxx-yyyy-2-1 -> xxxx-yyyy春季学期
            
            Args:
                zxjxjhh: 学期代码，如 "2025-2026-1-1"
                
            Returns:
                str: 转换后的学期名称，如 "2025-2026秋季学期"
            """
            try:
                parts = zxjxjhh.split("-")
                if len(parts) >= 3:
                    year_start = parts[0]
                    year_end = parts[1]
                    semester_num = parts[2]
                    
                    if semester_num == "1":
                        return f"{year_start}-{year_end}秋季学期"
                    elif semester_num == "2":
                        return f"{year_start}-{year_end}春季学期"
                        
                return zxjxjhh  # 如果格式不匹配，返回原值
            except Exception:
                return zxjxjhh
            
        try:
            logger.info("开始获取培养方案信息")

            headers = self._get_default_headers()

            # 使用重试机制获取培养方案基本信息
            plan_response = await self.vpn_connection.model_request(
                model=TrainingPlanResponseWrapper,
                url=f"{self.base_url}/main/showPyfaInfo?sf_request_type=ajax",
                method="GET",
                headers=headers,
                follow_redirects=True,
            )

            if not plan_response or plan_response.count <= 0 or not plan_response.data:
                return _create_error_plan_info("未获取到培养方案信息")
                
            plan_data_list = plan_response.data[0]
            if len(plan_data_list) < 2:
                return _create_error_plan_info("培养方案信息数据格式不正确")
                
            plan_name = plan_data_list[0]
            plan_id = plan_data_list[1]

            logger.info(f"培养方案信息获取成功: {plan_name} (ID: {plan_id})")

            # 提取年级信息 - 假设格式为"20XX级..."
            grade_match = re.search(r"(\d{4})级", plan_name)
            grade = grade_match.group(1) if grade_match else ""

            # 提取专业名称 - 假设格式为"20XX级XXX本科培养方案"
            major_match = re.search(r"\d{4}级(.+?)本科", plan_name)
            major_name = major_match.group(1) if major_match else ""

            # 获取学术信息来补全学期和课程数量信息
            term_name = ""
            course_count = 0
            
            try:
                # 调用学术信息接口获取当前学期和课程数量
                academic_response = await self.vpn_connection.requester().post(
                    f"{self.base_url}/main/academicInfo?sf_request_type=ajax",
                    headers=headers,
                    data={"flag": ""},
                    follow_redirects=True,
                )
                
                if academic_response.status_code == 200:
                    academic_data = academic_response.json()
                    if academic_data and isinstance(academic_data, list) and len(academic_data) > 0:
                        academic_item = academic_data[0]
                        
                        # 获取学期代码并转换格式
                        zxjxjhh = academic_item.get("zxjxjhh", "")
                        if zxjxjhh:
                            term_name = _convert_term_format(zxjxjhh)
                            logger.info(f"从学术信息获取学期: {zxjxjhh} -> {term_name}")
                        
                        # 获取课程数量
                        course_count = academic_item.get("courseNum", 0)
                        logger.info(f"从学术信息获取课程数量: {course_count}")
                        
            except Exception as e:
                logger.warning(f"获取学术信息补全培养方案失败: {str(e)}")
                # 使用默认值
                term_name = "当前学期"

            # 转换为TrainingPlanInfo格式返回
            return TrainingPlanInfo(
                pyfa=plan_name,
                major=major_name,
                grade=grade,
                term=term_name,
                courseCount=course_count,
            )
            
        except (AUFEConnectionError, AUFEParseError) as e:
            logger.error(f"获取培养方案信息失败: {str(e)}")
            return _create_error_plan_info(f"请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"获取培养方案信息异常: {str(e)}")
            return _create_error_plan_info()

    @activity_tracker
    @retry_async()
    async def check_course_selection_status(self) -> Optional[CourseSelectionStatus]:
        """
        检查选课状态

        Returns:
            Optional[CourseSelectionStatus]: 选课状态信息，失败时返回None
            
        Raises:
            AUFEConnectionError: 连接失败
            AUFEParseError: 数据解析失败
        """
        try:
            logger.info("开始检查选课状态")

            headers = self._get_default_headers()

            response = await self.vpn_connection.requester().post(
                f"{self.base_url}/main/checkSelectCourseStatus?sf_request_type=ajax",
                headers=headers,
                data={},  # 空POST请求
                follow_redirects=True,  # 处理可能的重定向
            )

            if response.status_code != 200:
                raise AUFEConnectionError(f"检查选课状态失败，状态码: {response.status_code}")

            json_data = response.json()
            try:
                # 解析新的选课状态响应格式
                status_response = CourseSelectionStatusDirectResponse.parse_obj(
                    json_data
                )

                # 解析选课状态码 - "0"表示不可选, "1"表示可选
                can_select = status_response.status_code == "1"

                logger.info(
                    f"选课状态检查成功: 当前学期={status_response.term_name}, 可选课={can_select}"
                )

                # 返回兼容的选课状态对象
                return CourseSelectionStatus(
                    isCanSelect=can_select,
                    startTime="",  # API未提供
                    endTime="",  # API未提供
                )
            except Exception as e:
                logger.error(f"解析选课状态异常: {str(e)}")
                raise AUFEParseError(f"选课状态解析失败: {str(e)}") from e
        except (AUFEConnectionError, AUFEParseError):
            raise
        except Exception as e:
            logger.error(f"检查选课状态异常: {str(e)}")
            raise AUFEConnectionError(f"检查选课状态失败: {str(e)}") from e

    @activity_tracker
    @retry_async()
    async def get_token(self) -> Optional[str]:
        """
        获取CSRF Token

        Returns:
            Optional[str]: CSRF Token，失败时返回None
            
        Raises:
            AUFEConnectionError: 连接失败
            AUFEParseError: Token解析失败
        """
        try:
            headers = self._get_default_headers()

            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/student/teachingEvaluation/evaluation/index",
                headers=headers,
                follow_redirects=True,  # 处理可能的重定向
            )

            if response.status_code != 200:
                raise AUFEConnectionError(f"获取Token失败，状态码: {response.status_code}")

            html = response.text

            # 使用简单字符串匹配查找token
            token_start = html.find('id="tokenValue" value="')
            if token_start != -1:
                token_start += 24  # len('id="tokenValue" value="')
                token_end = html.find('"', token_start)
                if token_end != -1:
                    token = html[token_start:token_end]
                    if token:
                        logger.info(f"获取Token成功: {token[:5]}***{token[-5:]}")
                        return token

            raise AUFEParseError("未找到Token值")
            
        except (AUFEConnectionError, AUFEParseError):
            raise
        except Exception as e:
            logger.error(f"获取Token异常: {str(e)}")
            raise AUFEConnectionError(f"获取Token失败: {str(e)}") from e

    @activity_tracker
    @retry_async()
    async def fetch_evaluation_course_list(self) -> List[Course]:
        """
        获取课程列表

        Returns:
            List[Course]: 课程列表
            
        Raises:
            AUFEConnectionError: 连接失败
            AUFEParseError: 数据解析失败
        """
        try:
            headers = self._get_default_headers()

            data = {"optType": "1", "pagesize": "50"}  # 增加页面大小以获取更多课程

            response = await self.vpn_connection.requester().post(
                f"{self.base_url}/student/teachingEvaluation/teachingEvaluation/search?sf_request_type=ajax",
                headers=headers,
                data=data,
                follow_redirects=True,  # 处理可能的重定向
            )

            if response.status_code != 200:
                raise AUFEConnectionError(f"获取课程列表失败，状态码: {response.status_code}")

            json_data = response.json()

            try:
                course_response = CourseListResponse.parse_obj(json_data)
                self.course_list_response = course_response

                logger.info(
                    f"获取课程成功，总数: {len(course_response.data)}，未完成: {course_response.not_finished_num}，总评价数: {course_response.evaluation_num}"
                )
                return course_response.data
            except Exception as e:
                logger.error(f"解析课程列表JSON异常: {str(e)}")
                raise AUFEParseError(f"课程列表解析失败: {str(e)}") from e
                
        except (AUFEConnectionError, AUFEParseError) as e:
            logger.error(f"获取课程列表失败: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"获取课程列表异常: {str(e)}")
            return []

    async def access_evaluation_page(self, token: str, course: Course) -> bool:
        """
        访问评价页面（准备评价）

        Args:
            token: CSRF Token
            course: 课程信息

        Returns:
            bool: 是否成功访问
        """
        try:
            evaluated_people = course.evaluated_people
            evaluated_people_number = course.id.evaluated_people if course.id else ""
            questionnaire_code = (
                course.questionnaire.questionnaire_number
                if course.questionnaire
                else ""
            )
            questionnaire_name = (
                course.questionnaire.questionnaire_name if course.questionnaire else ""
            )
            coure_sequence_number = course.id.coure_sequence_number if course.id else ""
            evaluation_content_number = (
                course.id.evaluation_content_number if course.id else ""
            )

            # 使用从课程列表获取的评价总数
            evaluation_count = (
                str(self.course_list_response.evaluation_num)
                if self.course_list_response
                else "28"
            )

            headers = self._get_default_headers()

            data = {
                "count": evaluation_count,
                "evaluatedPeople": evaluated_people,
                "evaluatedPeopleNumber": evaluated_people_number,
                "questionnaireCode": questionnaire_code,
                "questionnaireName": questionnaire_name,
                "coureSequenceNumber": coure_sequence_number,
                "evaluationContentNumber": evaluation_content_number,
                "evaluationContentContent": "",
                "tokenValue": token,
            }

            response = await self.vpn_connection.requester().post(
                f"{self.base_url}/student/teachingEvaluation/teachingEvaluation/evaluationPage",
                headers=headers,
                data=data,
                follow_redirects=True,  # 处理可能的重定向
            )

            is_success = response.status_code == 200

            logger.info(
                f"访问评价页面{'成功' if is_success else '失败'}: {questionnaire_name or course.evaluation_content}, 使用count={evaluation_count}"
            )
            return is_success
        except Exception as e:
            logger.error(f"访问评价页面异常: {str(e)}")
            return False

    async def submit_evaluation(
        self, evaluation_param: EvaluationRequestParam
    ) -> EvaluationResponse:
        """
        提交课程评价

        Args:
            evaluation_param: 评价请求参数

        Returns:
            EvaluationResponse: 评价提交响应
        """
        try:
            form_data = evaluation_param.to_form_data()

            headers = self._get_default_headers()

            response = await self.vpn_connection.requester().post(
                f"{self.base_url}/student/teachingEvaluation/teachingEvaluation/assessment?sf_request_type=ajax",
                headers=headers,
                data=form_data,
                follow_redirects=True,  # 处理可能的重定向
            )

            if response.status_code != 200:
                logger.error(f"提交评价失败: HTTP状态码 {response.status_code}")
                return EvaluationResponse(
                    result="error", msg=f"网络请求失败 ({response.status_code})"
                )

            json_data = response.json()
            eval_response = EvaluationResponse.parse_obj(json_data)

            logger.info(f"评价提交结果: {eval_response.result} - {eval_response.msg}")
            return eval_response
        except Exception as e:
            logger.error(f"提交评价异常: {str(e)}")
            return EvaluationResponse(result="error", msg=f"请求异常: {str(e)}")

    async def fetch_unified_exam_info(
        self, start_date: str, end_date: str, term_code: str = "2024-2025-2-1"
    ) -> ExamInfoResponse:
        """
        获取统一的考试信息，包括校统考和其他考试

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            term_code: 学期代码，默认为当前学期

        Returns:
            ExamInfoResponse: 统一的考试信息响应
        """
        try:
            # 获取校统考信息
            school_exams = await self._fetch_school_exam_schedule(start_date, end_date)
            
            # 获取座位号信息
            seat_info = await self._fetch_exam_seat_info()

            # 获取其他考试信息
            other_exams = await self._fetch_other_exam_records(term_code)

            # 合并并转换为统一格式
            unified_exams = []

            # 处理校统考数据
            for exam in school_exams:
                unified_exam = self._convert_school_exam_to_unified(exam, seat_info)
                if unified_exam:
                    unified_exams.append(unified_exam)

            # 处理其他考试数据
            for record in other_exams:
                unified_exam = self._convert_other_exam_to_unified(record)
                if unified_exam:
                    unified_exams.append(unified_exam)

            # 按考试日期排序
            unified_exams.sort(key=lambda x: x.exam_date)

            return ExamInfoResponse(exams=unified_exams, total_count=len(unified_exams))

        except Exception as e:
            logger.error(f"获取考试信息异常: {str(e)}")
            return ExamInfoResponse(exams=[], total_count=0)

    async def _fetch_school_exam_schedule(
        self, start_date: str, end_date: str
    ) -> List[ExamScheduleItem]:
        """
        获取校统考考试安排

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            List[ExamScheduleItem]: 校统考列表
        """
        try:
            import time

            timestamp = int(time.time() * 1000)

            headers = {
                **self._get_default_headers(),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            }

            url = f"{self.base_url}/student/examinationManagement/examPlan/detail"
            params = {
                "start": start_date,
                "end": end_date,
                "_": str(timestamp),
                "sf_request_type": "ajax",
            }
            await self.vpn_connection.requester().get(
                "http://jwcxk2-aufe-edu-cn.vpn2.aufe.edu.cn:8118/student/examinationManagement/examPlan/index",
                follow_redirects=True,
                headers=headers,
            )
            response = await self.vpn_connection.requester().get(
                url, headers=headers, params=params, follow_redirects=True
            )

            if response.status_code != 200:
                logger.error(f"获取校统考信息失败: HTTP状态码 {response.status_code}")
                return []

            json_data = response.json()

            # 解析为ExamScheduleItem列表
            school_exams = []
            if isinstance(json_data, list):
                for item in json_data:
                    exam_item = ExamScheduleItem.parse_obj(item)
                    school_exams.append(exam_item)

            logger.info(f"获取校统考信息成功，共 {len(school_exams)} 场考试")
            return school_exams

        except Exception as e:
            logger.error(f"获取校统考信息异常: {str(e)}")
            return []

    async def _fetch_other_exam_records(self, term_code: str) -> List:
        """
        获取其他考试记录

        Args:
            term_code: 学期代码

        Returns:
            List: 其他考试记录列表
        """
        try:
            headers = {
                **self._get_default_headers(),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
            }

            data = {"zxjxjhh": term_code, "tab": "0", "pageNum": "1", "pageSize": "30"}

            response = await self.vpn_connection.requester().post(
                f"{self.base_url}/student/examinationManagement/othersExamPlan/queryScores?sf_request_type=ajax",
                headers=headers,
                data=data,
                follow_redirects=True,
            )

            if response.status_code != 200:
                logger.error(f"获取其他考试信息失败: HTTP状态码 {response.status_code}")
                return []

            json_data = response.json()
            exam_response = OtherExamResponse.parse_obj(json_data)

            logger.info(
                f"获取其他考试信息成功，共 {len(exam_response.records)} 条记录"
            )
            return exam_response.records

        except Exception as e:
            logger.error(f"获取其他考试信息异常: {str(e)}")
            return []

    async def _fetch_exam_seat_info(self) -> Dict[str, str]:
        """
        获取考试座位号信息
        
        Returns:
            Dict[str, str]: 课程名到座位号的映射
        """
        try:
            headers = {
                **self._get_default_headers(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            }
            
            url = f"{self.base_url}/student/examinationManagement/examPlan/index"
            
            response = await self.vpn_connection.requester().get(
                url, headers=headers, follow_redirects=True
            )
            
            if response.status_code != 200:
                logger.error(f"获取考试座位号信息失败: HTTP状态码 {response.status_code}")
                return {}
                
            # 解析HTML获取座位号信息
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(response.text, "html.parser")
            seat_info = {}
            
            # 查找所有考试信息区块
            exam_blocks = soup.find_all("div", {"class": "widget-box"})
            for block in exam_blocks:
                course_name = ""
                seat_number = ""
                
                # 获取课程名
                title = block.find("h5", {"class": "widget-title"})  # type: ignore
                if title:
                    course_text = title.get_text(strip=True)  # type: ignore
                    # 提取课程名，格式可能是: "（课程代码-班号）课程名"
                    if "）" in course_text:
                        course_name = course_text.split("）", 1)[1].strip()
                    else:
                        course_name = course_text.strip()
                
                # 获取座位号
                widget_main = block.find("div", {"class": "widget-main"})  # type: ignore
                if widget_main:
                    content = widget_main.get_text()  # type: ignore
                    for line in content.split("\n"):
                        if "座位号" in line:
                            try:
                                seat_number = line.split("座位号:")[1].strip()
                            except Exception:
                                try:
                                    seat_number = line.split("座位号：")[1].strip()
                                except Exception:
                                    pass
                            break
                
                if course_name and seat_number:
                    seat_info[course_name] = seat_number
            
            logger.info(f"获取考试座位号信息成功，共 {len(seat_info)} 条记录")
            return seat_info
            
        except Exception as e:
            logger.error(f"获取考试座位号信息异常: {str(e)}")
            return {}

    def _convert_school_exam_to_unified(
        self, exam: ExamScheduleItem, seat_info: Optional[Dict[str, str]] = None
    ) -> Optional[UnifiedExamInfo]:
        """
        将校统考数据转换为统一格式

        Args:
            exam: 校统考项目
            seat_info: 座位号信息映射

        Returns:
            Optional[UnifiedExamInfo]: 统一格式的考试信息
        """
        try:
            # 解析title信息，格式如: "新媒体导论\n08:30-10:30\n西校\n西校通慧楼\n通慧楼-308\n"
            title_parts = exam.title.strip().split("\n")
            if len(title_parts) < 2:
                return None

            course_name = title_parts[0]
            exam_time = title_parts[1] if len(title_parts) > 1 else ""

            # 拼接地点信息
            location_parts = title_parts[2:] if len(title_parts) > 2 else []
            exam_location = " ".join([part for part in location_parts if part.strip()])
            
            # 添加座位号到备注
            note = ""
            if seat_info and course_name in seat_info:
                note = f"座位号: {seat_info[course_name]}"

            return UnifiedExamInfo(
                course_name=course_name,
                exam_date=exam.start,
                exam_time=exam_time,
                exam_location=exam_location,
                exam_type="校统考",
                note=note,
            )

        except Exception as e:
            logger.error(f"转换校统考数据异常: {str(e)}")
            return None

    def _convert_other_exam_to_unified(self, record) -> Optional[UnifiedExamInfo]:
        """
        将其他考试记录转换为统一格式

        Args:
            record: 其他考试记录

        Returns:
            Optional[UnifiedExamInfo]: 统一格式的考试信息
        """
        try:
            return UnifiedExamInfo(
                course_name=record.course_name,
                exam_date=record.exam_date,
                exam_time=record.exam_time,
                exam_location=record.exam_location,
                exam_type="其他考试",
                note=record.note,
            )

        except Exception as e:
            logger.error(f"转换其他考试数据异常: {str(e)}")
            return None

    # ==================== 学期和成绩相关方法 ====================

    async def fetch_all_terms(self) -> Dict[str, str]:
        """
        获取所有学期信息

        Returns:
            Dict[str, str]: 学期ID到学期名称的映射
        """

        try:
            url = f"{self.base_url}/student/courseSelect/calendarSemesterCurriculum/index"

            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en-US;q=0.7,en;q=0.6",
                "Cache-Control": "max-age=0",
                "Connection": "keep-alive",
                "Referer": f"{self.base_url}/student/integratedQuery/scoreQuery/scoreCard/index",
                "Upgrade-Insecure-Requests": "1",
                **self._get_default_headers(),
            }

            response = await self.vpn_connection.requester().get(
                url, headers=headers, follow_redirects=True
            )

            if response.status_code != 200:
                logger.error(f"获取学期信息失败，状态码: {response.status_code}")
                return {}

            # 解析HTML获取学期选项
            soup = BeautifulSoup(response.text, "html.parser")

            # 查找学期选择下拉框
            select_element = soup.find("select", {"id": "planCode"})
            if not select_element:
                logger.error("未找到学期选择框")
                return {}

            terms = {}
            # 使用更安全的方式处理选项
            try:
                options = select_element.find_all("option")  # type: ignore
                for option in options:
                    value = option.get("value")  # type: ignore
                    text = option.get_text(strip=True)  # type: ignore

                    # 跳过空值选项（如"全部"）
                    if value and str(value).strip() and text != "全部":
                        terms[str(value)] = text
            except AttributeError:
                logger.error("解析学期选项失败")
                return {}

            logger.info(f"成功获取{len(terms)}个学期信息")
            # 将学期中的 "春" 替换为 "下" ， "秋" 替换为 "上"
            for key, value in terms.items():
                terms[key] = value.replace("春", "下").replace("秋", "上")
            return terms

        except Exception as e:
            logger.error(f"获取学期信息异常: {str(e)}")
            return {}

    async def fetch_term_score(
        self,
        term_id: str,
        course_code: str = "",
        course_name: str = "",
        page_num: int = 1,
        page_size: int = 50,
    ) -> Optional[Dict]:
        """
        获取指定学期的成绩信息

        Args:
            term_id: 学期ID，如：2024-2025-2-1
            course_code: 课程代码（可选，用于筛选）
            course_name: 课程名称（可选，用于筛选）
            page_num: 页码，默认为1
            page_size: 每页大小，默认为50

        Returns:
            Optional[Dict]: 成绩数据
        """
        from bs4 import BeautifulSoup

        try:
            # 首先需要获取正确的URL中的动态路径参数
            # 这通常需要先访问成绩查询页面来获取
            initial_url = f"{self.base_url}/student/integratedQuery/scoreQuery/allTermScores/index"

            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en-US;q=0.7,en;q=0.6",
                **self._get_default_headers(),
            }

            # 先访问成绩查询页面
            response = await self.vpn_connection.requester().get(
                initial_url, headers=headers, follow_redirects=True
            )
            if response.status_code != 200:
                logger.error(f"访问成绩查询页面失败，状态码: {response.status_code}")
                return None

            # 从页面中提取动态路径参数
            soup = BeautifulSoup(response.text, "html.parser")

            # 查找表单或Ajax请求的URL
            # 通常在JavaScript代码中或表单action中
            dynamic_path = "M1uwxk14o6"  # 默认值，如果无法提取则使用

            # 尝试从页面中提取动态路径
            scripts = soup.find_all("script")
            for script in scripts:
                try:
                    script_text = script.string  # type: ignore
                    if script_text and "allTermScores/data" in script_text:
                        # 使用正则表达式提取路径
                        match = re.search(
                            r"/([A-Za-z0-9]+)/allTermScores/data", script_text
                        )
                        if match:
                            dynamic_path = match.group(1)
                            break
                except AttributeError:
                    continue

            # 构建成绩数据请求URL
            data_url = f"{self.base_url}/student/integratedQuery/scoreQuery/{dynamic_path}/allTermScores/data"

            # 请求成绩数据
            data_headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en-US;q=0.7,en;q=0.6",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.base_url,
                "Referer": initial_url,
                **self._get_default_headers(),
                "X-Requested-With": "XMLHttpRequest",
            }

            data_params = {
                "zxjxjhh": term_id,
                "kch": course_code,
                "kcm": course_name,
                "pageNum": str(page_num),
                "pageSize": str(page_size),
                "sf_request_type": "ajax",
            }

            data_response = await self.vpn_connection.requester().post(
                data_url, headers=data_headers, data=data_params, follow_redirects=True
            )

            if data_response.status_code != 200:
                logger.error(f"获取成绩数据失败，状态码: {data_response.status_code}")
                return None

            result = data_response.json()
            logger.info(f"成功获取学期 {term_id} 的成绩数据")
            return result

        except Exception as e:
            logger.error(f"获取学期成绩异常: {str(e)}")
            return None

    # ==================== 课表相关方法 ====================

    async def fetch_student_schedule(self, plan_code: str) -> Optional[Dict]:
        """
        获取学生课表信息

        Args:
            plan_code: 培养方案代码，如：2024-2025-2-1

        Returns:
            Optional[Dict]: 课表数据
        """
        try:
            logger.info(f"开始获取课表信息，培养方案代码: {plan_code}")

            # 首先需要获取动态路径参数
            # 先访问课表页面
            initial_url = f"{self.base_url}/student/courseSelect/calendarSemesterCurriculum/index"
            
            headers = {
                **self._get_default_headers(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Upgrade-Insecure-Requests": "1",
            }

            response = await self.vpn_connection.requester().get(
                initial_url, headers=headers, follow_redirects=True
            )
            if response.status_code != 200:
                logger.error(f"访问课表页面失败，状态码: {response.status_code}")
                return None

            # 从页面中提取动态路径参数
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 查找动态路径参数
            dynamic_path = "B2RMNJkT95"  # 默认值
            
            # 尝试从页面中提取动态路径
            scripts = soup.find_all("script")
            for script in scripts:
                try:
                    script_text = script.string  # type: ignore
                    if script_text and "ajaxStudentSchedule" in script_text:
                        # 使用正则表达式提取路径
                        match = re.search(
                            r"/([A-Za-z0-9]+)/ajaxStudentSchedule", script_text
                        )
                        if match:
                            dynamic_path = match.group(1)
                            break
                except AttributeError:
                    continue

            # 构建课表数据请求URL
            schedule_url = f"{self.base_url}/student/courseSelect/thisSemesterCurriculum/{dynamic_path}/ajaxStudentSchedule/past/callback"

            # 请求课表数据
            schedule_headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.base_url,
                "Pragma": "no-cache",
                "Referer": initial_url,
                **self._get_default_headers(),
                "X-Requested-With": "XMLHttpRequest",
            }

            schedule_params = {
                "planCode": plan_code,
                "sf_request_type": "ajax",
            }

            schedule_response = await self.vpn_connection.requester().post(
                schedule_url, headers=schedule_headers, data=schedule_params, follow_redirects=True
            )

            if schedule_response.status_code != 200:
                logger.error(f"获取课表数据失败，状态码: {schedule_response.status_code}")
                return None

            schedule_data = schedule_response.json()
            logger.info("成功获取课表数据")
            return schedule_data

        except Exception as e:
            logger.error(f"获取课表数据异常: {str(e)}")
            return None

    async def fetch_section_and_time(self) -> Optional[Dict]:
        """
        获取时间段信息

        Returns:
            Optional[Dict]: 时间段数据
        """
        try:
            logger.info("开始获取时间段信息")

            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.base_url,
                "Pragma": "no-cache",
                "Referer": f"{self.base_url}/student/courseSelect/calendarSemesterCurriculum/index",
                **self._get_default_headers(),
                "X-Requested-With": "XMLHttpRequest",
            }

            data = {
                "planNumber": "",
                "ff": "f",
                "sf_request_type": "ajax",
            }

            response = await self.vpn_connection.requester().post(
                f"{self.base_url}/ajax/getSectionAndTime",
                headers=headers,
                data=data,
                follow_redirects=True,
            )

            if response.status_code != 200:
                logger.error(f"获取时间段信息失败，状态码: {response.status_code}")
                return None

            time_data = response.json()
            logger.info("成功获取时间段信息")
            return time_data

        except Exception as e:
            logger.error(f"获取时间段信息异常: {str(e)}")
            return None

    async def fetch_course_schedule(self, plan_code: str) -> Optional[Dict]:
        """
        获取聚合的课表信息（课程数据 + 时间段数据）

        Args:
            plan_code: 培养方案代码，如：2024-2025-2-1

        Returns:
            Optional[Dict]: 聚合的课表数据
        """
        try:
            logger.info(f"开始获取聚合课表信息，培养方案代码: {plan_code}")

            # 并行获取课程数据和时间段数据
            schedule_data, time_data = await asyncio.gather(
                self.fetch_student_schedule(plan_code),
                self.fetch_section_and_time(),
                return_exceptions=True,
            )

            # 检查是否有异常
            if isinstance(schedule_data, Exception):
                logger.error(f"获取课程数据异常: {str(schedule_data)}")
                return None
            if isinstance(time_data, Exception):
                logger.error(f"获取时间段数据异常: {str(time_data)}")
                return None

            if not schedule_data or not time_data:
                logger.error("未能获取到完整的课表数据")
                return None

            # 聚合数据
            aggregated_data = {
                "schedule": schedule_data,
                "time_sections": time_data,
            }

            logger.info("成功获取聚合课表数据")
            return aggregated_data

        except Exception as e:
            logger.error(f"获取聚合课表数据异常: {str(e)}")
            return None

    def _process_schedule_data(self, raw_data: Dict) -> Optional[Dict]:
        """
        处理和过滤课表数据

        Args:
            raw_data: 原始聚合数据

        Returns:
            Optional[Dict]: 处理后的课表数据
        """
        try:
            schedule_data = raw_data.get("schedule", {})
            time_data = raw_data.get("time_sections", {})

            if not schedule_data or not time_data:
                logger.error("缺少必要的课表数据")
                return None

            # 处理时间段信息
            time_slots = []
            section_time = time_data.get("sectionTime", [])
            for time_slot in section_time:
                time_slots.append({
                    "session": time_slot.get("id", {}).get("session", 0),
                    "session_name": time_slot.get("sessionName", ""),
                    "start_time": time_slot.get("startTime", ""),
                    "end_time": time_slot.get("endTime", ""),
                    "time_length": time_slot.get("timeLength", ""),
                    "djjc": time_slot.get("djjc", 0),
                })

            # 处理课程信息
            courses = []
            xkxx_list = schedule_data.get("xkxx", [])
            
            for xkxx_item in xkxx_list:
                if isinstance(xkxx_item, dict):
                    for course_key, course_data in xkxx_item.items():
                        if isinstance(course_data, dict):
                            # 提取基本课程信息
                            course_name = course_data.get("courseName", "")
                            course_code = course_data.get("id", {}).get("coureNumber", "")
                            course_sequence = course_data.get("id", {}).get("coureSequenceNumber", "")
                            teacher_name = course_data.get("attendClassTeacher", "").replace("* ", "").strip()
                            course_properties = course_data.get("coursePropertiesName", "")
                            exam_type = course_data.get("examTypeName", "")
                            unit = float(course_data.get("unit", 0))

                            # 处理时间地点列表
                            time_locations = []
                            time_place_list = course_data.get("timeAndPlaceList", [])
                            
                            # 检查是否有具体时间安排
                            is_no_schedule = len(time_place_list) == 0
                            
                            for time_place in time_place_list:
                                # 过滤掉无用的字段，只保留关键信息
                                time_location = {
                                    "class_day": time_place.get("classDay", 0),
                                    "class_sessions": time_place.get("classSessions", 0),
                                    "continuing_session": time_place.get("continuingSession", 0),
                                    "class_week": time_place.get("classWeek", ""),
                                    "week_description": time_place.get("weekDescription", ""),
                                    "campus_name": time_place.get("campusName", ""),
                                    "teaching_building_name": time_place.get("teachingBuildingName", ""),
                                    "classroom_name": time_place.get("classroomName", ""),
                                }
                                time_locations.append(time_location)

                            # 只保留有效的课程（有课程名称的）
                            if course_name:
                                course = {
                                    "course_name": course_name,
                                    "course_code": course_code,
                                    "course_sequence": course_sequence,
                                    "teacher_name": teacher_name,
                                    "course_properties": course_properties,
                                    "exam_type": exam_type,
                                    "unit": unit,
                                    "time_locations": time_locations,
                                    "is_no_schedule": is_no_schedule,
                                }
                                courses.append(course)

            # 提取学期信息
            semester_info = {}
            section_info = time_data.get("section", {})
            if section_info:
                semester_info = {
                    "total_weeks": str(section_info.get("zs", 0)),
                    "week_description": section_info.get("zcsm", ""),
                    "total_sessions": str(section_info.get("tjc", 0)),
                    "first_day": str(time_data.get("firstday", 1)),
                }

            # 构建最终数据
            processed_data = {
                "total_units": float(schedule_data.get("allUnits", 0)),
                "time_slots": time_slots,
                "courses": courses,
                "semester_info": semester_info,
            }

            logger.info(f"成功处理课表数据：共{len(courses)}门课程，{len(time_slots)}个时间段")
            return processed_data

        except Exception as e:
            logger.error(f"处理课表数据异常: {str(e)}")
            return None

    async def get_processed_schedule(self, plan_code: str) -> Optional[Dict]:
        """
        获取处理后的课表数据

        Args:
            plan_code: 培养方案代码，如：2024-2025-2-1

        Returns:
            Optional[Dict]: 处理后的课表数据
        """
        try:
            # 获取原始聚合数据
            raw_data = await self.fetch_course_schedule(plan_code)
            if not raw_data:
                return None

            # 处理数据
            processed_data = self._process_schedule_data(raw_data)
            return processed_data

        except Exception as e:
            logger.error(f"获取处理后的课表数据异常: {str(e)}")
            return None

    # ==================== 培养方案完成情况相关方法 ====================

    @activity_tracker
    @retry_async()
    async def fetch_plan_completion_info(self) -> PlanCompletionInfo:
        """
        获取培养方案完成情况信息，使用重试机制

        Returns:
            PlanCompletionInfo: 培养方案完成情况信息，失败时返回错误模型
        """
        def _create_error_completion_info(error_msg: str = "请求失败，请稍后重试") -> ErrorPlanCompletionInfo:
            """创建错误培养方案完成情况信息"""
            return ErrorPlanCompletionInfo(
                plan_name=error_msg,
                major="请求失败",
                grade="",
                total_categories=-1,
                total_courses=-1,
                passed_courses=-1,
                failed_courses=-1,
                unread_courses=-1
            )
            
        try:
            logger.info("开始获取培养方案完成情况信息")

            headers = self._get_default_headers()

            # 请求培养方案完成情况页面
            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/student/integratedQuery/planCompletion/index",
                headers=headers,
                follow_redirects=True,
            )

            if response.status_code != 200:
                raise AUFEConnectionError(f"获取培养方案完成情况页面失败，状态码: {response.status_code}")

            html_content = response.text
            
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, "html.parser")

            # 提取培养方案名称
            plan_name = ""
            
            # 查找包含"培养方案"的h4标签
            h4_elements = soup.find_all("h4")
            for h4 in h4_elements:
                text = h4.get_text(strip=True) if h4 else ""
                if "培养方案" in text:
                    plan_name = text
                    logger.info(f"找到培养方案标题: {plan_name}")
                    break

            # 解析专业和年级信息
            major = ""
            grade = ""
            if plan_name:
                grade_match = re.search(r"(\d{4})级", plan_name)
                if grade_match:
                    grade = grade_match.group(1)
                
                major_match = re.search(r"\d{4}级(.+?)本科", plan_name)
                if major_match:
                    major = major_match.group(1)

            # 查找zTree数据
            ztree_data = []
            
            # 在script标签中查找zTree初始化数据
            scripts = soup.find_all("script")
            for script in scripts:
                try:
                    script_text = script.get_text() if script else ""
                    if "$.fn.zTree.init" in script_text and "flagId" in script_text:
                        logger.info("找到包含zTree初始化的script标签")
                        
                        # 提取zTree数据
                        # 尝试多种模式匹配
                        patterns = [
                            r'\$\.fn\.zTree\.init\(\$\("#treeDemo"\),\s*setting,\s*(\[.*?\])\s*\);',
                            r'\.zTree\.init\([^,]+,\s*[^,]+,\s*(\[.*?\])\s*\);',
                            r'init\(\$\("#treeDemo"\)[^,]*,\s*[^,]*,\s*(\[.*?\])',
                        ]
                        
                        json_part = None
                        for pattern in patterns:
                            match = re.search(pattern, script_text, re.DOTALL)
                            if match:
                                json_part = match.group(1)
                                logger.info(f"使用模式匹配成功提取zTree数据: {len(json_part)}字符")
                                break
                        
                        if json_part:
                            # 清理和修复JSON格式
                            # 移除JavaScript注释和多余的逗号
                            json_part = re.sub(r'//.*?\n', '\n', json_part)
                            json_part = re.sub(r'/\*.*?\*/', '', json_part, flags=re.DOTALL)
                            json_part = re.sub(r',\s*}', '}', json_part)
                            json_part = re.sub(r',\s*]', ']', json_part)
                            
                            try:
                                ztree_data = json.loads(json_part)
                                logger.info(f"JSON解析成功，共{len(ztree_data)}个节点")
                                break
                            except json.JSONDecodeError as e:
                                logger.warning(f"JSON解析失败: {str(e)}")
                                # 如果JSON解析失败，不使用手动解析，直接跳过
                                continue
                        else:
                            logger.warning("未能通过模式匹配提取zTree数据")
                            continue
                except Exception:
                    continue

            if not ztree_data:
                logger.warning("未找到有效的zTree数据")
                
                # 输出调试信息
                logger.debug(f"HTML内容长度: {len(html_content)}")
                logger.debug(f"找到的script标签数量: {len(soup.find_all('script'))}")
                
                # 检查是否包含关键词
                contains_ztree = "zTree" in html_content
                contains_flagid = "flagId" in html_content
                contains_plan = "培养方案" in html_content
                
                logger.debug(f"HTML包含关键词: zTree={contains_ztree}, flagId={contains_flagid}, 培养方案={contains_plan}")
                
                if contains_plan:
                    logger.warning("检测到培养方案内容，但zTree数据解析失败，可能页面结构已变化")
                else:
                    logger.warning("未检测到培养方案相关内容，可能需要重新登录或检查访问权限")
                    
                return _create_error_completion_info("未找到培养方案数据，请检查登录状态或访问权限")

            # 解析zTree数据构建分类和课程信息
            completion_info = self._build_completion_info_from_ztree(
                ztree_data, plan_name, major, grade
            )
            
            logger.info(
                f"培养方案完成情况获取成功: {completion_info.plan_name}, "
                f"总分类数: {completion_info.total_categories}, "
                f"总课程数: {completion_info.total_courses}"
            )
            
            return completion_info
            
        except (AUFEConnectionError, AUFEParseError) as e:
            logger.error(f"获取培养方案完成情况失败: {str(e)}")
            return _create_error_completion_info(f"请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"获取培养方案完成情况异常: {str(e)}")
            return _create_error_completion_info()

    def _build_completion_info_from_ztree(
        self, 
        ztree_data: List[dict], 
        plan_name: str, 
        major: str, 
        grade: str
    ) -> PlanCompletionInfo:
        """从zTree数据构建培养方案完成情况信息"""
        try:
            # 按层级组织数据
            nodes_by_id = {node["id"]: node for node in ztree_data}
            root_categories = []
            
            # 统计根分类和所有节点信息，用于调试
            all_parent_ids = set()
            root_nodes = []
            
            for node in ztree_data:
                parent_id = node.get("pId", "")
                all_parent_ids.add(parent_id)
                
                # 根分类的判断条件：pId为"-1"（这是zTree中真正的根节点标识）
                # 从HTML示例可以看出，真正的根分类的pId是"-1"
                is_root_category = parent_id == "-1"
                
                if is_root_category:
                    root_nodes.append(node)
            
            logger.info(f"zTree数据分析: 总节点数={len(ztree_data)}, 根节点数={len(root_nodes)}, 不同父ID数={len(all_parent_ids)}")
            logger.debug(f"所有父ID: {sorted(all_parent_ids)}")
            
            # 构建分类树
            for node in root_nodes:
                category = PlanCompletionCategory.from_ztree_node(node)
                self._populate_category_children(category, node["id"], nodes_by_id)
                root_categories.append(category)
                logger.debug(f"创建根分类: {category.category_name} (ID: {node['id']})")
            
            # 创建完成情况信息
            completion_info = PlanCompletionInfo(
                plan_name=plan_name,
                major=major,
                grade=grade,
                categories=root_categories,
                total_categories=0,
                total_courses=0,
                passed_courses=0,
                failed_courses=0,
                unread_courses=0
            )
            
            # 计算统计信息
            completion_info.calculate_statistics()
            
            return completion_info
            
        except Exception as e:
            logger.error(f"构建培养方案完成情况信息异常: {str(e)}")
            return ErrorPlanCompletionInfo(
                plan_name="解析失败",
                major="解析失败", 
                grade="",
                total_categories=-1,
                total_courses=-1,
                passed_courses=-1,
                failed_courses=-1,
                unread_courses=-1
            )

    def _populate_category_children(
        self, 
        category: PlanCompletionCategory, 
        category_id: str, 
        nodes_by_id: dict
    ):
        """填充分类的子分类和课程（支持多层嵌套）"""
        try:
            children_count = 0
            subcategory_count = 0
            course_count = 0
            
            for node in nodes_by_id.values():
                if node.get("pId") == category_id:
                    children_count += 1
                    flag_type = node.get("flagType", "")
                    
                    if flag_type in ["001", "002"]:  # 分类或子分类
                        subcategory = PlanCompletionCategory.from_ztree_node(node)
                        # 递归处理子项，支持多层嵌套
                        self._populate_category_children(subcategory, node["id"], nodes_by_id)
                        category.subcategories.append(subcategory)
                        subcategory_count += 1
                    elif flag_type == "kch":  # 课程
                        course = PlanCompletionCourse.from_ztree_node(node)
                        category.courses.append(course)
                        course_count += 1
                    else:
                        # 处理其他类型的节点，也可能是分类
                        # 根据是否有子节点来判断是分类还是课程
                        has_children = any(n.get("pId") == node["id"] for n in nodes_by_id.values())
                        if has_children:
                            # 有子节点，当作分类处理
                            subcategory = PlanCompletionCategory.from_ztree_node(node)
                            self._populate_category_children(subcategory, node["id"], nodes_by_id)
                            category.subcategories.append(subcategory)
                            subcategory_count += 1
                        else:
                            # 无子节点，当作课程处理
                            course = PlanCompletionCourse.from_ztree_node(node)
                            category.courses.append(course)
                            course_count += 1
            
            if children_count > 0:
                logger.debug(f"分类 '{category.category_name}' (ID: {category_id}) 的子项: 总数={children_count}, 子分类={subcategory_count}, 课程={course_count}")
                        
        except Exception as e:
            logger.error(f"填充分类子项异常: {str(e)}")
            logger.error(f"异常节点信息: category_id={category_id}, 错误详情: {str(e)}")

    async def fetch_semester_week_info(self) -> SemesterWeekInfo:
        """
        获取当前学期周数信息

        Returns:
            SemesterWeekInfo: 学期周数信息，失败时返回错误模型
        """
        def _create_error_week_info(error_msg: str = "请求失败，请稍后重试") -> ErrorSemesterWeekInfo:
            """创建错误学期周数信息"""
            return ErrorSemesterWeekInfo(
                academic_year=error_msg,
                semester="请求失败",
                week_number=-1,
                is_end=False,
                weekday="请求失败",
                raw_text=""
            )
            
        try:
            logger.info("开始获取学期周数信息")

            headers = self._get_default_headers()

            # 请求主页以获取当前学期周数信息
            response = await self.vpn_connection.requester().get(
                f"{self.base_url}/",
                headers=headers,
                follow_redirects=True,
            )

            if response.status_code != 200:
                raise AUFEConnectionError(f"获取学期周数信息页面失败，状态码: {response.status_code}")

            html_content = response.text
            
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, "html.parser")

            # 查找包含学期周数信息的元素
            # 使用CSS选择器查找
            calendar_element = soup.select_one("#navbar-container > div.navbar-buttons.navbar-header.pull-right > ul > li.light-red > a")
            
            if not calendar_element:
                # 如果CSS选择器失败，尝试其他方法
                # 查找包含"第X周"的元素
                potential_elements = soup.find_all("a", class_="dropdown-toggle")
                calendar_element = None
                
                for element in potential_elements:
                    text = element.get_text(strip=True) if element else ""
                    if "第" in text and "周" in text:
                        calendar_element = element
                        break
                
                # 如果还是找不到，尝试查找任何包含学期信息的元素
                if not calendar_element:
                    all_elements = soup.find_all(text=re.compile(r'\d{4}-\d{4}.*第\d+周'))
                    if all_elements:
                        # 找到包含学期信息的文本，查找其父元素
                        for text_node in all_elements:
                            parent = text_node.parent
                            if parent:
                                calendar_element = parent
                                break

            if not calendar_element:
                logger.warning("未找到学期周数信息元素")
                
                # 尝试在整个页面中搜索学期信息模式
                semester_pattern = re.search(r'(\d{4}-\d{4})\s*(春|秋|夏)?\s*第(\d+)周\s*(星期[一二三四五六日天])?', html_content)
                if semester_pattern:
                    calendar_text = semester_pattern.group(0)
                    logger.info(f"通过正则表达式找到学期信息: {calendar_text}")
                else:
                    logger.debug(f"HTML内容长度: {len(html_content)}")
                    logger.debug("未检测到学期周数相关内容，可能需要重新登录或检查访问权限")
                    return _create_error_week_info("未找到学期周数信息，请检查登录状态或访问权限")
            else:
                # 提取文本内容
                calendar_text = calendar_element.get_text(strip=True)
                logger.info(f"找到学期周数信息: {calendar_text}")

            # 解析学期周数信息
            week_info = SemesterWeekInfo.from_calendar_text(calendar_text)
            
            logger.info(
                f"学期周数信息获取成功: {week_info.academic_year} {week_info.semester} "
                f"第{week_info.week_number}周 {week_info.weekday}, 是否结束: {week_info.is_end}"
            )
            
            return week_info
            
        except (AUFEConnectionError, AUFEParseError) as e:
            logger.error(f"获取学期周数信息失败: {str(e)}")
            return _create_error_week_info(f"请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"获取学期周数信息异常: {str(e)}")
            return _create_error_week_info()
