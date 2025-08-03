import datetime
from typing import Optional

from sqlalchemy import func, String, Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from database.base import Base


class User(Base):
    __tablename__ = "user_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    userid: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    easyconnect_password: Mapped[str] = mapped_column(String(255), nullable=False)
    create_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now())


class UserProfile(Base):
    __tablename__ = "user_profile_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    userid: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    avatar_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用户头像文件名")
    background_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用户背景文件名")
    nickname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="用户昵称")
    settings_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用户设置文件名")
    create_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    update_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Invite(Base):
    __tablename__ = "invite_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    invite_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    create_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now())


class AuthME(Base):
    __tablename__ = "authme_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    userid: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    authme_token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="设备/会话标识符")
    create_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now())


class AACTicket(Base):
    __tablename__ = "aac_ticket_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    userid: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    aac_token: Mapped[str] = mapped_column(String(500), nullable=False)
    create_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
