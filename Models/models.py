from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id : Mapped[int] = mapped_column(primary_key=True)
    nome_utente : Mapped[str] = mapped_column(String(50))
    password : Mapped[str] = mapped_column(String)
    email : Mapped[str] = mapped_column(unique=True)
    notification_tokens = relationship(
        "NotificationToken",
        back_populates="user",
        cascade="all, delete"
    )

class Task(Base):
    __tablename__ = "tasks"

    id_task : Mapped[int] = mapped_column(Integer, primary_key=True)
    task_datetime : Mapped[datetime] = mapped_column(DateTime(timezone=True))
    titolo : Mapped[str] = mapped_column(String(50))
    descrizione : Mapped[str] = mapped_column(String)
    completato : Mapped[bool] = mapped_column(Boolean,default=False)
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id"))
    isRepeating : Mapped[bool] = mapped_column(Boolean)
    every : Mapped[int] = mapped_column(Integer,nullable= True)
    option : Mapped[String] = mapped_column(Integer,nullable= True)



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






