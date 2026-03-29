from typing import List
from datetime import timedelta,datetime
from dateutil.relativedelta import relativedelta
from Service.Socket import SocketManage, manager
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status
from datetime import datetime, timezone
from typing import Optional
from Models.models import NotificationToken
from Routers.user import get_current_user
from Schemas.schemas import Task, CreaTask, TokenRequest, UpdateTask, GetTask
from database import SessionLocal
from services.push_service import send_service

router = APIRouter( prefix="/task", tags=["Task"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

'''
@router.get("/test-push")
def test_push():

    token = "BIVxRaBeZAcD1fgB_cN9lxW9sS5OGVcj2rnChfbx299AItSJWB_Hwy96ZqPQJFinZRBgJ8xxYPFgYPYiFJRoIzw"

    send_service(token,"title","ciao")

    return {"status": "sent"}

@router.post("/create-token")
def create_token(data: TokenRequest,db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    exist = db.query(NotificationToken).filter( NotificationToken.token == data.token ).first()
    if exist:
        return {"status":"Token già registrato"}

    newtoken = NotificationToken(token = data.token, id_user_ref = current_user['id_utente'])
    db.add(newtoken)
    db.commit()

    return {"status":"Token creato"}

'''
@router.get("/ping")
def ping():
    return {"ok":1}

def to_utc(dt: Optional[datetime]):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

@router.post("/crea_task", response_model = CreaTask)
def crea_task(task: CreaTask, db = Depends(get_db), current_user = Depends(get_current_user)):
    print(" CREA TASK CHIAMATA")
    print(f"accesso effettuato come {current_user['email']}")
    print(f"id  {current_user['id_utente']}")
    if not current_user['email'] or not current_user['id_utente']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        # L'orario di creazione del task lo faccio generare a lui
        db_task = Task(titolo = task.titolo, 
                       descrizione = task.descrizione, 
                       creation_task_datetime = to_utc(task.creation_task_datetime ), 
                       task_datetime_repeat = to_utc(task.task_datetime_repeat) , 
                       completato = task.completato,
                       user_id = current_user['id_utente'],
                       isRepeating = task.isRepeating, 
                       every = task.every, 
                       option = task.option,
                       end_recurrency_time = task.end_recurrency_time,
                       dateTime_task_end = to_utc(task.dateTime_task_end)
                       )
       
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
    except Exception as e:
        db.rollback()
        print(f"errore {e}")

    return db_task

@router.get("/tutti_task", response_model = List[GetTask])
def visualizza_tasks( db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"accesso effettuato come {current_user['email']}")
    return db.query(Task).filter(Task.user_id == current_user['id_utente']).all()

@router.get("/visualizza_task", response_model = List[GetTask])
def visualizza_tasks( db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"accesso effettuato come {current_user['email']}")
    return db.query(Task).filter(Task.user_id == current_user['id_utente'], Task.completato == False).all()

@router.get("/task_completati", response_model = List[GetTask])
def task_completati( db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"accesso effettuato come {current_user['email']}")
    return db.query(Task).filter(Task.user_id == current_user['id_utente'], Task.completato == True).all()


# todo provare per la modifica del singolo task se aggiorna datetime_task_last_update durante lo scarico degli aggiornamenti
@router.patch("/modifica_task")
async def modifica_task(id_task:int,task_update: UpdateTask, db = Depends(get_db), current_user = Depends(get_current_user)):

    print(f"accesso effettuato come {current_user['email']}")
    task_db = db.query(Task).filter(Task.id_task == id_task,Task.user_id == current_user['id_utente']).first()
    if task_update.isToUpdate:
        print("isToUpdate è vero, aggiorno data modifica")
        task_update.datetime_task_last_update = datetime.now(timezone.utc)
    else:
        print("isToUpdate è false, non aggiorno data modifica")
    print(f"aggiornamento ore utc {datetime.now(timezone.utc)}")
    print(f"aggiornamento ore {datetime.now()}")

    update_data = task_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        print(f"${key} - ${value}\n")

    update_data.pop("id_task", None)
    update_data.pop("user_id", None)
    
    for key, value in update_data.items():
        if isinstance(value, datetime):
            value = to_utc(value)
        setattr(task_db, key, value)

    db.commit()
    db.refresh(task_db)

    await manager.send_update_task_to_user(current_user['id_utente'],{"task_id": task_db.id_task ,"type": "updated_task"})
   
    
    return {"msg":"Valori Aggiornati"}


# todo aggiornare per data ripetizione
@router.patch("/update_change_notify")
async def update_change_notify(id_task:int,task_update: UpdateTask, db = Depends(get_db), current_user = Depends(get_current_user)):

    print(f"accesso effettuato come {current_user['email']}")
    task_db = db.query(Task).filter(Task.id_task == id_task,Task.user_id == current_user['id_utente']).first()
    update_data = task_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        print(f"${key} - ${value}\n")

    update_data.pop("id_task", None)
    update_data.pop("user_id", None)
    
    
    for key, value in update_data.items():
        if isinstance(value, datetime):
            value = to_utc(value)
        setattr(task_db, key, value)
    db.commit()
    db.refresh(task_db)

    return {"msg":"Valori Aggiornati"}


@router.delete("/elimina_task/{id_task}")
async def elimina_task(id_task:int, db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"accesso effettuato come {current_user['email']}")
    print(f"id  {current_user['id_utente']} task ${id_task} taskdb ${Task.id_task} ")
    task_db = db.query(Task).filter(Task.id_task == id_task,Task.user_id == current_user['id_utente']).first()
    if not task_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task non trovato")

    db.delete(task_db)
    db.commit()

    return {"msg":"Task eliminato"}
   

