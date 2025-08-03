from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class AcademicDataItem(BaseModel):
    """学术信息数据项，用于直接反序列化JSON数组中的元素"""

    completed_courses: int = Field(0, alias="courseNum")
    failed_courses: int = Field(0, alias="coursePas")
    gpa: float = Field(0, alias="gpa")
    current_term: str = Field("", alias="zxjxjhh")
    pending_courses: int = Field(0, alias="courseNum_bxqyxd")


class AcademicInfo(BaseModel):
    """学术信息数据模型 - 兼容旧版API"""

    completed_courses: int = Field(0, alias="count")
    failed_courses: int = Field(0, alias="countNotPass")
    gpa: float = Field(0, alias="gpa")


# ==================== 学期和成绩相关模型 ====================


class TermInfo(BaseModel):
    """学期信息模型"""

    term_id: str = Field("", description="学期ID，如：2024-2025-2-1")
    term_name: str = Field("", description="学期名称，如：2024-2025春季学期")


class ScoreRecord(BaseModel):
    """成绩记录模型"""

    sequence: int = Field(0, description="序号")
    term_id: str = Field("", description="学期ID")
    course_code: str = Field("", description="课程代码")
    course_class: str = Field("", description="课程班级")
    course_name_cn: str = Field("", description="课程名称（中文）")
    course_name_en: str = Field("", description="课程名称（英文）")
    credits: str = Field("", description="学分")
    hours: int = Field(0, description="学时")
    course_type: str = Field("", description="课程性质")
    exam_type: str = Field("", description="考试性质")
    score: str = Field("", description="成绩")
    retake_score: Optional[str] = Field(None, description="重修成绩")
    makeup_score: Optional[str] = Field(None, description="补考成绩")


class TermScoreResponse(BaseModel):
    """学期成绩响应模型"""

    page_size: int = Field(50, description="每页大小")
    page_num: int = Field(1, description="页码")
    total_count: int = Field(0, description="总记录数")
    records: List[ScoreRecord] = Field(default_factory=list, description="成绩记录列表")


# ==================== 原有模型继续 ====================


class TrainingPlanDataItem(BaseModel):
    """培养方案数据项"""

    plan_name: str = ""  # 第一项为培养方案名称
    plan_id: str = ""  # 第二项为培养方案ID


class TrainingPlanResponseWrapper(BaseModel):
    """培养方案响应模型"""

    count: int = 0
    data: List[List[str]] = []


class TrainingPlanInfo(BaseModel):
    """培养方案信息模型 - 兼容旧版API"""

    plan_name: str = Field("", alias="pyfa")
    current_term: str = Field("", alias="term")
    pending_courses: int = Field(0, alias="courseCount")
    major_name: str = Field("", alias="major")
    grade: str = Field("", alias="grade")


class CourseSelectionStatusDirectResponse(BaseModel):
    """选课状态响应模型新格式"""

    term_name: str = Field("", alias="zxjxjhm")
    status_code: str = Field("", alias="retString")


class CourseSelectionStatus(BaseModel):
    """选课状态信息"""

    can_select: bool = Field(False, alias="isCanSelect")
    start_time: str = Field("", alias="startTime")
    end_time: str = Field("", alias="endTime")


class CourseId(BaseModel):
    """课程ID信息"""

    evaluated_people: str = Field("", alias="evaluatedPeople")
    coure_sequence_number: str = Field("", alias="coureSequenceNumber")
    evaluation_content_number: str = Field("", alias="evaluationContentNumber")


class Questionnaire(BaseModel):
    """问卷信息"""

    questionnaire_number: str = Field("", alias="questionnaireNumber")
    questionnaire_name: str = Field("", alias="questionnaireName")


class Course(BaseModel):
    """课程基本信息"""

    id: Optional[CourseId] = None
    questionnaire: Optional[Questionnaire] = Field(None, alias="questionnaire")
    evaluated_people: str = Field("", alias="evaluatedPeople")
    is_evaluated: str = Field("", alias="isEvaluated")
    evaluation_content: str = Field("", alias="evaluationContent")


class CourseListResponse(BaseModel):
    """课程列表响应"""

    not_finished_num: int = Field(0, alias="notFinishedNum")
    evaluation_num: int = Field(0, alias="evaluationNum")
    data: List[Course] = Field(default_factory=list, alias="data")
    msg: str = Field("", alias="msg")
    result: str = "success"  # 设置默认值


class EvaluationResponse(BaseModel):
    """评价提交响应"""

    result: str = ""
    msg: str = ""
    data: Any = None


class EvaluationRequestParam(BaseModel):
    """评价请求参数"""

    opt_type: str = "submit"
    token_value: str = ""
    questionnaire_code: str = ""
    evaluation_content: str = ""
    evaluated_people_number: str = ""
    count: str = ""
    zgpj: str = ""
    rating_items: Dict[str, str] = {}

    def to_form_data(self) -> Dict[str, str]:
        """将对象转换为表单数据映射"""
        form_data = {
            "optType": self.opt_type,
            "tokenValue": self.token_value,
            "questionnaireCode": self.questionnaire_code,
            "evaluationContent": self.evaluation_content,
            "evaluatedPeopleNumber": self.evaluated_people_number,
            "count": self.count,
            "zgpj": self.zgpj,
        }
        # 添加评分项
        form_data.update(self.rating_items)
        return form_data


class ExamScheduleItem(BaseModel):
    """考试安排项目 - 校统考格式"""

    title: str = ""  # 考试标题，包含课程名、时间、地点等信息
    start: str = ""  # 考试日期 (YYYY-MM-DD)
    color: str = ""  # 显示颜色


class OtherExamRecord(BaseModel):
    """其他考试记录"""

    term_code: str = Field("", alias="ZXJXJHH")  # 学期代码
    term_name: str = Field("", alias="ZXJXJHM")  # 学期名称
    exam_name: str = Field("", alias="KSMC")  # 考试名称
    course_code: str = Field("", alias="KCH")  # 课程代码
    course_name: str = Field("", alias="KCM")  # 课程名称
    class_number: str = Field("", alias="KXH")  # 课序号
    student_id: str = Field("", alias="XH")  # 学号
    student_name: str = Field("", alias="XM")  # 姓名
    exam_location: str = Field("", alias="KSDD")  # 考试地点
    exam_date: str = Field("", alias="KSRQ")  # 考试日期
    exam_time: str = Field("", alias="KSSJ")  # 考试时间
    note: str = Field("", alias="BZ")  # 备注
    row_number: str = Field("", alias="RN")  # 行号


class OtherExamResponse(BaseModel):
    """其他考试查询响应"""

    page_size: int = Field(0, alias="pageSize")
    page_num: int = Field(0, alias="pageNum")
    page_context: Dict[str, int] = Field(default_factory=dict, alias="pageContext")
    records: List[OtherExamRecord] = Field(default_factory=list, alias="records")


class UnifiedExamInfo(BaseModel):
    """统一考试信息模型 - 对外提供的统一格式"""

    course_name: str = ""  # 课程名称
    exam_date: str = ""  # 考试日期 (YYYY-MM-DD)
    exam_time: str = ""  # 考试时间
    exam_location: str = ""  # 考试地点
    exam_type: str = ""  # 考试类型 (校统考/其他考试)
    note: str = ""  # 备注信息


class ExamInfoResponse(BaseModel):
    """考试信息统一响应模型"""

    exams: List[UnifiedExamInfo] = Field(default_factory=list)
    total_count: int = 0


# ==================== 错误响应模型 ====================


class ErrorAcademicInfo(AcademicInfo):
    """错误的学术信息数据模型"""

    completed_courses: int = Field(-1, alias="count")
    failed_courses: int = Field(-1, alias="countNotPass")
    gpa: float = Field(-1.0, alias="gpa")


class ErrorTrainingPlanInfo(TrainingPlanInfo):
    """错误的培养方案信息模型"""

    plan_name: str = Field("请求失败，请稍后重试", alias="pyfa")
    current_term: str = Field("", alias="term")
    pending_courses: int = Field(-1, alias="courseCount")
    major_name: str = Field("请求失败", alias="major")
    grade: str = Field("", alias="grade")


class ErrorCourseSelectionStatus(CourseSelectionStatus):
    """错误的选课状态信息"""

    can_select: bool = Field(False, alias="isCanSelect")
    start_time: str = Field("请求失败", alias="startTime")
    end_time: str = Field("请求失败", alias="endTime")


class ErrorCourse(Course):
    """错误的课程基本信息"""

    id: Optional[CourseId] = None
    questionnaire: Optional[Questionnaire] = None
    evaluated_people: str = Field("请求失败", alias="evaluatedPeople")
    is_evaluated: str = Field("否", alias="isEvaluated")
    evaluation_content: str = Field("请求失败，请稍后重试", alias="evaluationContent")


class ErrorCourseListResponse(CourseListResponse):
    """错误的课程列表响应"""

    not_finished_num: int = Field(-1, alias="notFinishedNum")
    evaluation_num: int = Field(-1, alias="evaluationNum")
    data: List[Course] = Field(default_factory=list, alias="data")
    msg: str = Field("网络请求失败，已进行多次重试", alias="msg")
    result: str = "failed"


class ErrorEvaluationResponse(EvaluationResponse):
    """错误的评价提交响应"""

    result: str = "failed"
    msg: str = "网络请求失败，已进行多次重试"
    data: Any = None


class ErrorExamInfoResponse(ExamInfoResponse):
    """错误的考试信息响应模型"""

    exams: List[UnifiedExamInfo] = Field(default_factory=list)
    total_count: int = -1


class ErrorTermScoreResponse(BaseModel):
    """错误的学期成绩响应模型"""

    page_size: int = Field(-1, description="每页大小")
    page_num: int = Field(-1, description="页码")
    total_count: int = Field(-1, description="总记录数")
    records: List[ScoreRecord] = Field(default_factory=list, description="成绩记录列表")
