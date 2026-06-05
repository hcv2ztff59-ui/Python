from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import IntEnum
from database import Base

class TaskPriority(IntEnum):
    low = 0
    medium = 1
    high = 2

class User(Base):
    __tablename__ = "users"

    id : Mapped[int] = mapped_column(primary_key=True)
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

    id_task : Mapped[int] = mapped_column(Integer, primary_key=True)
    #datetime di creazione dell'evento
    creation_task_datetime : Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # datetime di lancio evento
    task_datetime_repeat : Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    titolo : Mapped[str] = mapped_column(String(50))
    descrizione : Mapped[str] = mapped_column(String)
    completato : Mapped[bool] = mapped_column(Boolean,default=False)
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id"))
    # è un evento ripetuto??
    isRepeating : Mapped[bool] = mapped_column(Boolean)
    # ogni quanti giorni/settimane/mesi/anni
    every : Mapped[int] = mapped_column(Integer,nullable= True)
    # giorni/settimane/mesi/anni
    option : Mapped[String] = mapped_column(String,nullable= True)
    end_recurrency_time : Mapped[int] = mapped_column(Integer,nullable= True)
    priority: Mapped[int] = mapped_column(Integer,default=TaskPriority.medium.value)
    dateTime_task_end : Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    datetime_task_last_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
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






