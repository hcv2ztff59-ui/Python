from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr,field_serializer
from datetime import datetime, timezone

from Models.models import Task,User


class RegistraUtente(BaseModel):

    nome_utente : str
    email : EmailStr
    password : str

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


    class Config:
        from_attributes = True


class CreaTask(BaseModel):
    descrizione : str
    creation_task_datetime : datetime
    task_datetime_repeat : datetime
    titolo : str
    completato : bool = False
    user_id : int
    isRepeating : bool = False
    every : Optional[int] = None
    option : Optional[str] = None
    end_recurrency_time : Optional[int] = None
    dateTime_task_end : Optional[datetime] = None


    class Config:
        from_attributes = True

class GetTask(BaseModel):
    id_task : int
    descrizione : str
    creation_task_datetime : datetime
    task_datetime_repeat : datetime
    titolo : str
    completato : bool = False
    user_id : int
    isRepeating :bool = False
    every : Optional[int] = None
    option : Optional[str] = None
    end_recurrency_time : Optional[int] = None
    dateTime_task_end : Optional[datetime] = None
    datetime_task_last_update: Optional[datetime] = None

    @field_serializer("*", when_used="json")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return value
   


    class Config:
        from_attributes = True


class UpdateTask(BaseModel):
    descrizione : Optional[str] = None
    task_datetime_repeat : Optional[datetime] = None 
    titolo : Optional[str] = None
    completato : Optional[bool] = None
    user_id : Optional[int] = None
    isRepeating :bool = False
    every : Optional[int] = None
    option : Optional[str] = None
    end_recurrency_time : Optional[int] = None
    dateTime_task_end : Optional[datetime] = None
    datetime_task_last_update:  Optional[datetime] = None 

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