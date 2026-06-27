from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Text,Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import IntEnum
from database import Base
from sqlalchemy import UniqueConstraint

class TaskPriority(IntEnum):
    low = 0
    medium = 1
    high = 2

class User(Base):
    __tablename__ = "users"

    id : Mapped[int] = mapped_column(primary_key=True, index=True)
    nome_utente : Mapped[str] = mapped_column(String(50))
    creation_user_datetime : Mapped[datetime] = mapped_column(DateTime(timezone=True))
    password : Mapped[str] = mapped_column(String)
    email : Mapped[str] = mapped_column(unique=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(100),unique=True,nullable=True)
    image_profile : Mapped[Optional[str]] = mapped_column(String(200), nullable= True)
    updated_user_datetime : Mapped[Optional[datetime]]  = mapped_column(DateTime(timezone=True),nullable=True)
    notification_tokens = relationship(
        "NotificationToken",
        back_populates="user",
        cascade="all, delete"
    )

class Task(Base):
    __tablename__ = "tasks"

    id_task : Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    #datetime di creazione dell'evento
    creation_task_datetime : Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # datetime di lancio evento
    task_datetime_repeat : Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    completedAt : Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    titolo : Mapped[str] = mapped_column(String(50))
    descrizione : Mapped[str] = mapped_column(String)
    completato : Mapped[bool] = mapped_column(Boolean,default=False,index=True)
    notificationEnabled : Mapped[bool] = mapped_column(Boolean,default=False)
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id"),index=True)
    # è un evento ripetuto??
    isRepeating : Mapped[bool] = mapped_column(Boolean)
    # ogni quanti giorni/settimane/mesi/anni
    every : Mapped[int] = mapped_column(Integer,nullable= True)
    notify_before : Mapped[int] = mapped_column(Integer,nullable= True)
    # giorni/settimane/mesi/anni
    option : Mapped[String] = mapped_column(String,nullable= True)
    end_recurrency_time : Mapped[int] = mapped_column(Integer,nullable= True)
    category : Mapped[String] = mapped_column(String,nullable= True)
    location_name : Mapped[String] = mapped_column(String,nullable= True)
    longitude : Mapped[float] = mapped_column(Float,nullable= True)
    latitude : Mapped[float] = mapped_column(Float,nullable= True)
    isNearEnabled : Mapped[bool] = mapped_column(Boolean,default=False)
    priority: Mapped[int] = mapped_column(Integer,default=TaskPriority.medium.value)
    is_all_day: Mapped[bool] = mapped_column(Boolean)
    all_day_datetime: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    dateTime_task_end : Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    datetime_task_last_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    ) 
    mentions = relationship(

        "TaskMentions",

        back_populates="task",

        cascade="all, delete-orphan"

    )

class Follow(Base):
    __tablename__ = "follow"

    id : Mapped[int] = mapped_column(primary_key=True)
    follower_id : Mapped[int] = mapped_column(Integer,nullable= False,index=True)
    followed_id : Mapped[int] = mapped_column(Integer,nullable= False,index=True)
    request_accepted : Mapped[bool] = mapped_column(Boolean,nullable=False, default=False)
    created_at : Mapped[Optional[datetime]]  = mapped_column(DateTime(timezone=True),nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "follower_id",
            "followed_id",
            name="uq_follow_unique"
        ),
    )
   


class TaskMentions(Base):
    __tablename__ = "task_mentions"

    id: Mapped[int] = mapped_column(primary_key=True)

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id_task", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    mentioned_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    notification_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    task = relationship(
        "Task",
        back_populates="mentions"
    )

class NotificationToken(Base):
    __tablename__ = "notification_tokens"

    id : Mapped[int] = mapped_column(primary_key=True)
    fcm_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True
    )

    id_user_ref: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    user = relationship(
        "User",
        back_populates="notification_tokens"
    )






