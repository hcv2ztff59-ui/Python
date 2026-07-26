from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr,field_serializer
from datetime import datetime, timezone


from Models.models import Task,User, TaskPriority, Follow


class AddFriendRequest(BaseModel):
    followed_id: int
    
class ForgotPasswordRequest(BaseModel):

    email: str
    class Config:
        from_attributes = True

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    class Config:
     from_attributes = True
     
class Follower(BaseModel):
  
    id: int
    follower_id : int
    followed_id : int
    request_accepted : bool
    created_at : datetime
    class Config:
        from_attributes = True

class FollowResponse(BaseModel):
    follow_id: int
    accepted: bool
    class Config:
        from_attributes = True

class MentionCreate(BaseModel):

    mentioned_user_id: int

    created_by_user_id: int

    notification_read: bool = False

    created_at: datetime



class Mentions(BaseModel):
   
    id:int
    task_id : int
    mentioned_user_id : int
    created_by_user_id : int
    notification_read : bool = False
    created_at: datetime | None
    class Config:
        from_attributes = True
   

class RegistraUtente(BaseModel):

    nome_utente : str
    email : EmailStr
    password : str
    nickname: Optional[str] = None
    image_profile : Optional[str] = None
    class Config:
        from_attributes = True

class ModificaUtente(BaseModel):
    nome_utente: Optional[str] = None
    nickname: Optional[str] = None
    password: Optional[str] = None

    class Config:
        from_attributes = True
        
        
class Users(BaseModel):
    nome_utente: str
    id:int

    class Config:
        from_attributes = True

class Login(BaseModel):

    email : EmailStr
    password : str

    class Config:
        from_attributes = True

class UtenteNoPassw(BaseModel):

    nome_utente : str
    email : str
    nickname: Optional[str] = None
    image_profile: Optional[str] = None

    class Config:
        from_attributes = True


class CreaTask(BaseModel):
   
    descrizione : str
    creation_task_datetime : datetime
    task_datetime_repeat: datetime | None = None
    titolo : str
    completato : bool = False
    notificationEnabled : bool = False
    notify_before : Optional[int] = None
    priority: TaskPriority = TaskPriority.medium
   # user_id : int
    isRepeating : bool = False
    every : Optional[int] = None
    option : Optional[str] = None
    end_recurrency_time : Optional[int] = None
    dateTime_task_end : Optional[datetime] = None
    is_all_day: bool = False    
    category : Optional[str] = None
    all_day_datetime: Optional[datetime] = None
    location_name :Optional[str] = None
    longitude  : Optional[float] = None 
    latitude : Optional[float] = None 
    isNearEnabled : Optional[bool] = False 
    mentions: Optional[list[MentionCreate]] = []
    lastExpiredNotification : Optional[datetime] = None

    class Config:
        from_attributes = True

class GetTask(BaseModel):
    id_task : int
    descrizione : str
    creation_task_datetime : datetime
    task_datetime_repeat: datetime | None = None
    titolo : str
    completato : bool = False
    notificationEnabled : bool = False
    notify_before : Optional[int] = None
    user_id : int
    isRepeating :bool = False
    every : Optional[int] = None
    option : Optional[str] = None
    end_recurrency_time : Optional[int] = None
    dateTime_task_end : Optional[datetime] = None
    datetime_task_last_update: Optional[datetime] = None
    priority: TaskPriority
    completedAt : Optional[datetime] = None 
    is_all_day: bool = False    
    notify_before :Optional[int] = None
    category : Optional[str] = None
    all_day_datetime: Optional[datetime] = None
    location_name :Optional[str] = None
    longitude  : Optional[float] = None 
    latitude : Optional[float] = None 
    isNearEnabled : Optional[bool] = False 
    isDeleted : bool = False
    lastExpiredNotification : Optional[datetime] = None
     
    @field_serializer("*", when_used="json")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return value
   

    mentions: list[Mentions] = []

    class Config:

        from_attributes = True  
    


class UpdateTask(BaseModel):
    descrizione : Optional[str] = None
    task_datetime_repeat : Optional[datetime] = None 
    completedAt : Optional[datetime] = None 
    titolo : Optional[str] = None
    completato : Optional[bool] = None
    notificationEnabled : bool = None
    notify_before : Optional[int] = None
    user_id : Optional[int] = None
    isRepeating :bool = False
    every : Optional[int] = None
    option : Optional[str] = None
    end_recurrency_time : Optional[int] = None
    dateTime_task_end : Optional[datetime] = None
    datetime_task_last_update:  Optional[datetime] = None 
    isToUpdate : Optional[bool] = None
    priority: Optional[TaskPriority] = None
    is_all_day: bool = False    
    all_day_datetime: Optional[datetime] = None
    category : Optional[str]
    location_name :Optional[str] = None
    longitude  : Optional[float] = None 
    latitude : Optional[float] = None 
    isNearEnabled : Optional[bool] = False 
    mentions: Optional[list[MentionCreate]] = None
    isDeleted : Optional[bool] = None
    lastExpiredNotification : Optional[datetime] = None

    class Config:
        from_attributes = True

class RefreshRequest(BaseModel):
    refresh_token: str
    class Config:
        from_attributes = True

class TokenRequest(BaseModel):
    fcm_token: str
    class Config:
        from_attributes = True