import datetime

from sqlalchemy import func, String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from database.base import Base


class ISIMRoomBinding(Base):
    """ISIM系统房间绑定表"""
    __tablename__ = "isim_room_binding_table"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    userid: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="用户ID")
    building_code: Mapped[str] = mapped_column(String(10), nullable=False, comment="楼栋代码")
    building_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="楼栋名称")
    floor_code: Mapped[str] = mapped_column(String(10), nullable=False, comment="楼层代码")
    floor_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="楼层名称")
    room_code: Mapped[str] = mapped_column(String(20), nullable=False, comment="房间代码")
    room_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="房间名称")
    room_id: Mapped[str] = mapped_column(String(20), nullable=False, comment="房间ID（楼栋+楼层+房间）")
    create_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    update_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


# 注释：电费记录和充值记录都实时获取，不存储在数据库中
