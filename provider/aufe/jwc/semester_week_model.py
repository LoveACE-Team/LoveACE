from typing import Optional
from pydantic import BaseModel, Field
import re
from loguru import logger


class SemesterWeekInfo(BaseModel):
    """学期周数信息"""
    
    academic_year: str = Field("", description="学年，如 2025-2026")
    semester: str = Field("", description="学期，如 秋、春")
    week_number: int = Field(0, description="当前周数")
    is_end: bool = Field(False, description="是否为学期结束")
    weekday: str = Field("", description="星期几")
    raw_text: str = Field("", description="原始文本")
    
    def calculate_statistics(self):
        """计算统计信息（如果需要的话）"""
        pass

    @classmethod
    def from_calendar_text(cls, calendar_text: str) -> "SemesterWeekInfo":
        """从日历文本解析学期周数信息
        
        Args:
            calendar_text: 日历文本，例如 "2025-2026 秋  第1周   星期三"
            
        Returns:
            SemesterWeekInfo: 学期周数信息对象
        """
        # 清理文本
        clean_text = re.sub(r'\s+', ' ', calendar_text.strip())
        
        # 初始化默认值
        academic_year = ""
        semester = ""
        week_number = 0
        is_end = False
        weekday = ""
        
        try:
            # 解析学年：2025-2026
            year_match = re.search(r'(\d{4}-\d{4})', clean_text)
            if year_match:
                academic_year = year_match.group(1)
            
            # 解析学期：秋、春
            semester_match = re.search(r'(春|秋|夏)', clean_text)
            if semester_match:
                semester = semester_match.group(1)
            
            # 解析周数：第1周、第15周等
            week_match = re.search(r'第(\d+)周', clean_text)
            if week_match:
                week_number = int(week_match.group(1))
            
            # 解析星期：星期一、星期二等
            weekday_match = re.search(r'星期([一二三四五六日天])', clean_text)
            if weekday_match:
                weekday = weekday_match.group(1)
            
            # 判断是否为学期结束（通常第16周以后或包含"结束"等关键词）
            if week_number >= 16 or "结束" in clean_text or "考试" in clean_text:
                is_end = True
                
        except Exception as e:
            logger.warning(f"解析学期周数信息时出错: {str(e)}")
        
        return cls(
            academic_year=academic_year,
            semester=semester,
            week_number=week_number,
            is_end=is_end,
            weekday=weekday,
            raw_text=clean_text
        )


class ErrorSemesterWeekInfo(SemesterWeekInfo):
    """错误的学期周数信息"""
    
    academic_year: str = Field("解析失败", description="学年")
    semester: str = Field("解析失败", description="学期")
    week_number: int = Field(-1, description="当前周数")
    is_end: bool = Field(False, description="是否为学期结束")
    weekday: str = Field("解析失败", description="星期几")


class SemesterWeekResponse(BaseModel):
    """学期周数信息响应模型"""
    
    code: int = Field(0, description="响应码")
    message: str = Field("获取成功", description="响应消息")
    data: Optional[SemesterWeekInfo] = Field(None, description="学期周数数据")


class ErrorSemesterWeekResponse(BaseModel):
    """错误的学期周数信息响应"""
    
    code: int = Field(-1, description="响应码")
    message: str = Field("请求失败，请稍后重试", description="响应消息")
    data: Optional[ErrorSemesterWeekInfo] = Field(default=None, description="错误数据")
