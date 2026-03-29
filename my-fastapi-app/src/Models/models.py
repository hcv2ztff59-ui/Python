from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Task(Base):
    __tablename__ = 'tasks'

    id_task = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    titolo = Column(String, index=True)
    descrizione = Column(String)
    task_datetime = Column(DateTime, nullable=False)
    completato = Column(Boolean, default=False)

    user = relationship("User", back_populates="tasks")

class NotificationToken(Base):
    __tablename__ = 'notification_tokens'

    id = Column(Integer, primary_key=True, index=True)
    id_user_ref = Column(Integer, ForeignKey('users.id'), nullable=False)
    fcm_token = Column(String, nullable=False)

    user = relationship("User", back_populates="notification_tokens")