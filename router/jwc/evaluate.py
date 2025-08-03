from provider.aufe.jwc import JWCClient
from provider.aufe.jwc.model import Course, EvaluationRequestParam

import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class TaskStatus(Enum):
    """任务状态枚举"""

    IDLE = "idle"  # 空闲
    INITIALIZING = "initializing"  # 初始化中
    RUNNING = "running"  # 运行中
    PAUSED = "paused"  # 暂停
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败
    TERMINATED = "terminated"  # 已终止


@dataclass
class EvaluationStats:
    """评价统计信息"""

    total_courses: int = 0
    pending_courses: int = 0
    success_count: int = 0
    fail_count: int = 0
    current_index: int = 0
    status: TaskStatus = TaskStatus.IDLE
    message: str = ""
    course_list: List[Course] = field(default_factory=list)
    current_countdown: int = 0
    current_course: Optional[Course] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: str = ""


@dataclass
class CurrentCourseInfo:
    """当前评价课程信息"""

    is_evaluating: bool = False
    course_name: str = ""
    teacher_name: str = ""
    progress_text: str = ""
    countdown_seconds: int = 0
    current_index: int = -1
    total_pending: int = 0


class Constants:
    """常量定义"""

    # 等待评价的冷却时间（秒）
    COUNTDOWN_SECONDS = 140  # 2分20秒

    # 随机评价文案 - 总体评价文案
    ZGPGS = [
        "老师授课生动形象,课堂氛围活跃。",
        "教学方法新颖,能够激发学习兴趣。",
        "讲解耐心细致,知识点清晰易懂。",
        "对待学生公平公正,很有亲和力。",
        "课堂管理有序,效率高。",
        "能理论联系实际,深入浅出。",
        "作业布置合理,有助于巩固知识。",
        "教学经验丰富,讲解深入浅出。",
        "关注学生反馈,及时调整教学。",
        "教学资源丰富,便于学习。",
        "课堂互动性强,能充分调动积极性。",
        "教学重点突出,难点突破到位。",
        "性格开朗,课堂充满活力。",
        "批改作业认真,评语有指导性。",
        "教学目标明确,条理清晰。",
    ]

    # 额外描述性文案
    NICE_0000000200 = [
        "常把晦涩理论生活化,知识瞬间亲近起来。",
        "总用类比解难点,复杂概念秒懂。",
        "引入行业前沿案例,打开视野新窗口。",
        "设问巧妙引深思,激发自主探寻答案。",
        "常分享学科冷知识,拓宽知识边界。",
        "用跨学科视角解题,思维更灵动。",
        "鼓励尝试多元解法,创新思维被激活。",
        "常分享科研趣事,点燃学术热情。",
        "用思维导图梳理知识,结构一目了然。",
        "常把学习方法倾囊相授,效率直线提升。",
        "用历史事件类比,知识记忆更深刻。",
        "常鼓励跨学科学习,综合素养渐涨。",
        "分享行业大咖故事,奋斗动力满满。",
        "总能挖掘知识背后的趣味,学习味十足。",
        "常组织知识竞赛,学习热情被点燃。",
    ]

    # 建议文案
    NICE_0000000201 = [
        "无",
        "没有",
        "没有什么建议,老师很好",
        "继续保持这么好的教学风格",
        "希望老师继续分享更多精彩案例",
        "感谢老师的悉心指导",
    ]


class EvaluationTaskManager:
    """评价任务管理器 - 基于学号管理"""

    def __init__(self, jwc_client: JWCClient, user_id: str):
        """
        初始化评价任务管理器

        Args:
            jwc_client: JWC客户端实例
            user_id: 用户学号
        """
        self.jwc_client = jwc_client
        self.user_id = user_id
        self.stats = EvaluationStats()
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._progress_callbacks: List[Callable[[EvaluationStats], None]] = []

        logger.info(f"初始化评价任务管理器，用户ID: {user_id}")

    def add_progress_callback(self, callback: Callable[[EvaluationStats], None]):
        """添加进度回调函数"""
        self._progress_callbacks.append(callback)

    def _notify_progress(self):
        """通知所有进度回调"""
        for callback in self._progress_callbacks:
            try:
                callback(self.stats)
            except Exception as e:
                logger.error(f"进度回调执行失败: {str(e)}")

    async def initialize(self) -> bool:
        """
        初始化评价环境

        Returns:
            bool: 初始化是否成功
        """
        try:
            self.stats.status = TaskStatus.INITIALIZING
            self.stats.message = "正在检查网络..."
            self._notify_progress()

            # 检查网络连接
            if not await self.jwc_client.check_network_connection():
                self.stats.status = TaskStatus.FAILED
                self.stats.message = "网络连接失败，请确保连接到校园网或VPN"
                self.stats.error_message = "网络连接失败"
                self._notify_progress()
                return False

            # 验证环境和Cookie
            self.stats.message = "正在验证登录状态..."
            self._notify_progress()

            if not await self.jwc_client.validate_environment_and_cookie():
                self.stats.status = TaskStatus.FAILED
                self.stats.message = "登录状态失效，请重新登录"
                self.stats.error_message = "Cookie验证失败"
                self._notify_progress()
                return False

            # 获取Token
            self.stats.message = "正在获取Token..."
            self._notify_progress()

            token = await self.jwc_client.get_token()
            if not token:
                self.stats.status = TaskStatus.FAILED
                self.stats.message = "获取Token失败，可能是评教系统未开放"
                self.stats.error_message = "Token获取失败"
                self._notify_progress()
                return False

            # 获取课程列表
            self.stats.message = "正在获取课程列表..."
            self._notify_progress()

            courses = await self.jwc_client.fetch_evaluation_course_list()
            if not courses:
                self.stats.status = TaskStatus.FAILED
                self.stats.message = "未获取到课程列表，请稍后再试"
                self.stats.error_message = "课程列表获取失败"
                self._notify_progress()
                return False

            # 更新统计信息
            pending_courses = [
                course
                for course in courses
                if getattr(course, "is_evaluated", "否") != "是"
            ]
            self.stats.course_list = courses
            self.stats.total_courses = len(courses)
            self.stats.pending_courses = len(pending_courses)
            self.stats.status = TaskStatus.IDLE
            self.stats.message = (
                f"初始化完成，找到 {self.stats.pending_courses} 门待评价课程"
            )
            self.stats.current_course = None

            logger.info(
                f"用户 {self.user_id} 初始化完成，待评价课程: {self.stats.pending_courses}"
            )
            self._notify_progress()

            return True

        except Exception as e:
            self.stats.status = TaskStatus.FAILED
            self.stats.message = f"初始化异常: {str(e)}"
            self.stats.error_message = str(e)
            logger.error(f"用户 {self.user_id} 初始化失败: {str(e)}")
            self._notify_progress()
            return False

    async def evaluate_course(self, course: Course, token: str) -> bool:
        """
        评价单门课程

        Args:
            course: 课程信息
            token: CSRF Token

        Returns:
            bool: 评价是否成功
        """
        try:
            # 设置当前课程
            self.stats.current_course = course

            # 如果课程已评价，则跳过
            if getattr(course, "is_evaluated", "否") == "是":
                logger.info(f"课程已评价，跳过: {course.evaluation_content}")
                return True

            # 第一步：访问评价页面
            if not await self.jwc_client.access_evaluation_page(token, course):
                return False

            course_name = course.evaluation_content
            logger.info(f"正在准备评价: {course_name}")

            self.stats.message = "已访问评价页面，等待服务器倒计时完成后提交评价..."
            self._notify_progress()

            # 等待服务器倒计时
            server_wait_time = Constants.COUNTDOWN_SECONDS

            # 显示倒计时
            for second in range(server_wait_time, 0, -1):
                # 检查是否被终止
                if self._stop_event.is_set():
                    self.stats.status = TaskStatus.TERMINATED
                    self.stats.message = "任务已被终止"
                    self._notify_progress()
                    return False

                self.stats.current_countdown = second
                self.stats.message = f"服务器倒计时: {second} 秒，然后提交评价..."
                self._notify_progress()

                await asyncio.sleep(1)

            self.stats.current_countdown = 0
            self.stats.message = "倒计时结束，正在提交评价..."
            self._notify_progress()

            # 生成评价数据
            evaluation_ratings = {}
            for i in range(180, 202):
                key = f"0000000{i}"
                if i == 200:
                    evaluation_ratings[key] = random.choice(Constants.NICE_0000000200)
                elif i == 201:
                    evaluation_ratings[key] = random.choice(Constants.NICE_0000000201)
                else:
                    evaluation_ratings[key] = f"5_{random.choice(['0.8', '1'])}"

            # 创建评价请求参数
            evaluation_param = EvaluationRequestParam(
                token_value=token,
                questionnaire_code=(
                    course.questionnaire.questionnaire_number
                    if course.questionnaire
                    else ""
                ),
                evaluation_content=(
                    course.id.evaluation_content_number if course.id else ""
                ),
                evaluated_people_number=course.id.evaluated_people if course.id else "",
                zgpj=random.choice(Constants.ZGPGS),
                rating_items=evaluation_ratings,
            )

            # 提交评价
            response = await self.jwc_client.submit_evaluation(evaluation_param)
            success = response.result == "success"

            if success:
                logger.info(f"课程评价成功: {course_name}")
            else:
                logger.error(f"课程评价失败: {course_name}, 错误: {response.msg}")

            # 清除当前课程信息
            self.stats.current_course = None
            self.stats.current_countdown = 0

            return success

        except Exception as e:
            logger.error(f"评价课程异常: {str(e)}")
            return False

    async def start_evaluation_task(self) -> bool:
        """
        开始评价任务
        确保一个用户只能有一个运行中的任务

        Returns:
            bool: 任务是否成功启动
        """
        # 检查当前状态
        if self.stats.status == TaskStatus.RUNNING:
            logger.warning(f"用户 {self.user_id} 的评价任务已在运行中")
            return False

        if self.stats.status == TaskStatus.INITIALIZING:
            logger.warning(f"用户 {self.user_id} 的评价任务正在初始化中")
            return False

        # 检查是否有未完成的异步任务
        if self._task and not self._task.done():
            logger.warning(f"用户 {self.user_id} 已有任务在执行")
            return False

        # 确保任务已经初始化
        if self.stats.status == TaskStatus.IDLE and len(self.stats.course_list) == 0:
            logger.warning(f"用户 {self.user_id} 任务未初始化，请先调用initialize")
            return False

        # 重置停止事件
        self._stop_event.clear()

        # 创建新任务
        self._task = asyncio.create_task(self._evaluate_all_courses())

        logger.info(f"用户 {self.user_id} 开始评价任务")
        return True

    async def _evaluate_all_courses(self):
        """批量评价所有课程（内部方法）"""
        try:
            # 获取Token
            token = await self.jwc_client.get_token()
            if not token:
                self.stats.status = TaskStatus.FAILED
                self.stats.message = "获取Token失败"
                self._notify_progress()
                return

            # 获取待评价课程
            pending_courses = [
                course
                for course in self.stats.course_list
                if getattr(course, "is_evaluated", "否") != "是"
            ]

            if not pending_courses:
                self.stats.status = TaskStatus.COMPLETED
                self.stats.message = "所有课程已评价完成！"
                self._notify_progress()
                return

            # 开始评价流程
            self.stats.status = TaskStatus.RUNNING
            self.stats.success_count = 0
            self.stats.fail_count = 0
            self.stats.current_course = None
            self.stats.start_time = datetime.now()

            index = 0
            while index < len(pending_courses):
                # 检查是否被终止
                if self._stop_event.is_set():
                    self.stats.status = TaskStatus.TERMINATED
                    self.stats.message = "任务已被终止"
                    self.stats.end_time = datetime.now()
                    self._notify_progress()
                    return

                course = pending_courses[index]
                self.stats.current_index = index
                self.stats.current_course = course

                course_name = getattr(
                    course.questionnaire,
                    "questionnaire_name",
                    course.evaluation_content,
                )
                self.stats.message = f"正在处理第 {index + 1}/{len(pending_courses)} 门课程: {course_name}"
                self._notify_progress()

                # 评价当前课程
                success = await self.evaluate_course(course, token)

                if success:
                    self.stats.success_count += 1
                    self.stats.message = f"课程评价成功: {course_name}"
                else:
                    self.stats.fail_count += 1
                    self.stats.message = f"课程评价失败: {course_name}"

                self._notify_progress()

                # 评价完一门课程后，重新获取课程列表
                self.stats.message = "正在更新课程列表..."
                self._notify_progress()

                # 重新获取课程列表
                updated_courses = await self.jwc_client.fetch_evaluation_course_list()
                if updated_courses:
                    self.stats.course_list = updated_courses
                    pending_courses = [
                        course
                        for course in updated_courses
                        if getattr(course, "is_evaluated", "否") != "是"
                    ]
                    self.stats.total_courses = len(updated_courses)
                    self.stats.pending_courses = len(pending_courses)
                    self.stats.message = (
                        f"课程列表已更新，剩余待评价课程: {self.stats.pending_courses}"
                    )
                    self._notify_progress()

                # 给服务器一些处理时间
                if pending_courses and index < len(pending_courses) - 1:
                    self.stats.message = "准备处理下一门课程..."
                    self._notify_progress()
                    await asyncio.sleep(3)

                index += 1

            # 评价完成
            self.stats.status = TaskStatus.COMPLETED
            self.stats.current_course = None
            self.stats.end_time = datetime.now()
            self.stats.message = f"评价完成！成功: {self.stats.success_count}，失败: {self.stats.fail_count}"

            logger.info(
                f"用户 {self.user_id} 评价任务完成，成功: {self.stats.success_count}，失败: {self.stats.fail_count}"
            )
            self._notify_progress()

        except Exception as e:
            self.stats.status = TaskStatus.FAILED
            self.stats.error_message = str(e)
            self.stats.message = f"评价任务异常: {str(e)}"
            self.stats.end_time = datetime.now()
            logger.error(f"用户 {self.user_id} 评价任务异常: {str(e)}")
            self._notify_progress()

    async def pause_task(self) -> bool:
        """
        暂停任务

        Returns:
            bool: 是否成功暂停
        """
        if self.stats.status != TaskStatus.RUNNING:
            return False

        self.stats.status = TaskStatus.PAUSED
        self.stats.message = "任务已暂停"
        logger.info(f"用户 {self.user_id} 任务已暂停")
        self._notify_progress()
        return True

    async def resume_task(self) -> bool:
        """
        恢复任务

        Returns:
            bool: 是否成功恢复
        """
        if self.stats.status != TaskStatus.PAUSED:
            return False

        self.stats.status = TaskStatus.RUNNING
        self.stats.message = "任务已恢复"
        logger.info(f"用户 {self.user_id} 任务已恢复")
        self._notify_progress()
        return True

    async def terminate_task(self) -> bool:
        """
        终止任务

        Returns:
            bool: 是否成功终止
        """
        if self.stats.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            return False

        # 设置停止事件
        self._stop_event.set()

        # 如果有运行中的任务，等待其完成
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        self.stats.status = TaskStatus.TERMINATED
        self.stats.message = "任务已终止"
        self.stats.end_time = datetime.now()
        logger.info(f"用户 {self.user_id} 任务已终止")
        self._notify_progress()
        return True

    def get_current_course_info(self) -> CurrentCourseInfo:
        """
        获取当前评价课程信息

        Returns:
            CurrentCourseInfo: 当前课程信息
        """
        # 如果没有运行评价任务
        if self.stats.status != TaskStatus.RUNNING:
            return CurrentCourseInfo(
                is_evaluating=False, progress_text="当前无评价任务"
            )

        # 正在评价但还没有确定是哪门课程
        if (
            self.stats.current_index < 0
            or self.stats.current_index >= len(self.stats.course_list)
            or self.stats.current_course is None
        ):
            return CurrentCourseInfo(
                is_evaluating=True,
                progress_text="准备中...",
                total_pending=self.stats.pending_courses,
            )

        # 正在评价特定课程
        course = self.stats.current_course
        pending_courses = [
            c
            for c in self.stats.course_list
            if getattr(c, "is_evaluated", "否") != "是"
        ]
        index = self.stats.current_index + 1
        total = len(pending_courses)

        countdown_text = (
            f" (倒计时: {self.stats.current_countdown}秒)"
            if self.stats.current_countdown > 0
            else ""
        )

        course_name = course.evaluation_content[:20]
        if len(course.evaluation_content) > 20:
            course_name += "..."

        return CurrentCourseInfo(
            is_evaluating=True,
            course_name=course_name,
            teacher_name=course.evaluated_people,
            progress_text=f"正在评价({index}/{total}): {course_name} - {course.evaluated_people}{countdown_text}",
            countdown_seconds=self.stats.current_countdown,
            current_index=self.stats.current_index,
            total_pending=total,
        )

    def get_task_status(self) -> EvaluationStats:
        """
        获取任务状态

        Returns:
            EvaluationStats: 任务统计信息
        """
        return self.stats

    def get_user_id(self) -> str:
        """获取用户ID"""
        return self.user_id


# 全局任务管理器字典，以学号为键
_task_managers: Dict[str, EvaluationTaskManager] = {}


def get_task_manager(
    user_id: str, jwc_client: Optional[JWCClient] = None
) -> Optional[EvaluationTaskManager]:
    """
    获取或创建任务管理器
    一个用户只能有一个活跃的任务管理器

    Args:
        user_id: 用户学号
        jwc_client: JWC客户端（创建新管理器时需要）

    Returns:
        Optional[EvaluationTaskManager]: 任务管理器实例
    """
    if user_id in _task_managers:
        existing_manager = _task_managers[user_id]
        # 检查现有任务的状态
        current_status = existing_manager.get_task_status().status

        # 如果任务已完成、失败或终止，自动清理
        if current_status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.TERMINATED,
        ]:
            logger.info(f"自动清理用户 {user_id} 的已完成任务")
            del _task_managers[user_id]
        else:
            # 返回现有的管理器
            return existing_manager

    # 创建新的管理器
    if jwc_client is None:
        return None

    manager = EvaluationTaskManager(jwc_client, user_id)
    _task_managers[user_id] = manager
    logger.info(f"为用户 {user_id} 创建新的任务管理器")
    return manager


def remove_task_manager(user_id: str) -> bool:
    """
    移除任务管理器

    Args:
        user_id: 用户学号

    Returns:
        bool: 是否成功移除
    """
    if user_id in _task_managers:
        del _task_managers[user_id]
        return True
    return False


def get_all_task_managers() -> Dict[str, EvaluationTaskManager]:
    """获取所有任务管理器"""
    return _task_managers.copy()
