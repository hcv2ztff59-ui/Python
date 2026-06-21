from typing import List
from datetime import timedelta,datetime
from dateutil.relativedelta import relativedelta
from Service.Socket import manager
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import joinedload
from Models.models import NotificationToken, TaskMentions
from Routers.user import get_current_user
from Schemas.schemas import Task, CreaTask, TokenRequest, UpdateTask, GetTask, MentionCreate
from database import SessionLocal
from services.push_service import send_service

router = APIRouter( prefix="/task", tags=["Task"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/ping")
def ping():
    return {"ok":1}

def to_utc(dt: Optional[datetime]):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

@router.post("/crea_task", response_model = GetTask)
async def crea_task(task: CreaTask, db = Depends(get_db), current_user = Depends(get_current_user)):
    print(" CREA TASK CHIAMATA")
    print(f"accesso effettuato come {current_user['email']}")
    print(f"id  {current_user['id_utente']}")
    if not current_user['email'] or not current_user['id_utente']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    try:
        # L'orario di creazione del task lo faccio generare a lui
        db_task = Task(titolo = task.titolo, 
                       descrizione = task.descrizione if task.descrizione is not None else None, 
                       creation_task_datetime = to_utc(task.creation_task_datetime ), 
                       all_day_datetime = task.all_day_datetime,
                       is_all_day = task.is_all_day,
                       
                       task_datetime_repeat = (

                                to_utc(task.task_datetime_repeat)

                                if task.task_datetime_repeat

                                else None

                            ), 
                       completato = task.completato,
                       user_id = current_user['id_utente'],
                       notificationEnabled=task.notificationEnabled,
                       notify_before=task.notify_before,
                       isRepeating = task.isRepeating, 
                       priority = task.priority.value,
                       every = task.every, 
                       option = task.option,
                       end_recurrency_time = task.end_recurrency_time,
                       dateTime_task_end = to_utc(task.dateTime_task_end),
                       category = task.category,
                       location_name = task.location_name,
                       longitude = task.longitude,
                       latitude = task.latitude,
                       isNearEnabled = task.isNearEnabled
                       
                       )
       
        db.add(db_task)
        db.commit()
        db.refresh(db_task)

        mentions = [
            TaskMentions(
                task_id=db_task.id_task,
                mentioned_user_id=m.mentioned_user_id,
                created_by_user_id=m.created_by_user_id,
                notification_read=m.notification_read,
                created_at=m.created_at,
            )
            for m in (task.mentions or [])

        ]

        db.add_all(mentions)
        db.commit()
        db.refresh(db_task)
        
        for m in (task.mentions or []):
            print(f"Utente {m.mentioned_user_id} menzionato")
           
                  
        if manager.has_multiple_connections(current_user['id_utente']):
            await manager.send_new_task_to_user(current_user['id_utente'],{"task_id": db_task.id_task ,"type": "new_task"})
    except Exception as e:

        db.rollback()

        print(f"errore {e}")

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )

    return db_task

@router.get("/tutti_task", response_model = List[GetTask])
def visualizza_tasks( db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"accesso effettuato come {current_user['email']}")
    return db.query(Task).filter(Task.user_id == current_user['id_utente']).all()


@router.get("/tutti_task_filtered", response_model=List[GetTask])

def visualizza_tasks(

    db=Depends(get_db),

    current_user=Depends(get_current_user)

):

    return (

        db.query(Task)

        .options(joinedload(Task.mentions))

        .filter(Task.user_id == current_user["id_utente"])

        .all()

    )

# todo provare per la modifica del singolo task se aggiorna datetime_task_last_update durante lo scarico degli aggiornamenti
@router.patch("/modifica_task")
async def modifica_task(id_task:int,task_update: UpdateTask, db = Depends(get_db), current_user = Depends(get_current_user)):

    print(f"accesso effettuato come {current_user['email']}")
    task_db = db.query(Task).filter(Task.id_task == id_task,Task.user_id == current_user['id_utente']).first()
    if task_db is None:
        raise HTTPException(

            status_code=404,

            detail="Task non trovato"

        )

    if task_update.isToUpdate:
        print("isToUpdate è vero, aggiorno data modifica")
        task_update.datetime_task_last_update = datetime.now(timezone.utc)
    else:
        print("isToUpdate è false, non aggiorno data modifica")
    print(f"aggiornamento ore utc {datetime.now(timezone.utc)}")
    print(f"aggiornamento ore {datetime.now()}")

    update_data = task_update.model_dump(exclude_unset=True)

    mentions = update_data.pop("mentions", None)
    
    for key, value in update_data.items():
        print(f"${key} - ${value}\n")

    update_data.pop("id_task", None)
    update_data.pop("user_id", None)
    
    for key, value in update_data.items():
        if key == "priority" and value is not None:
            value = value.value
       # if key == "task_datetime_repeat" and value  is not None:
        #   value = value.value
        if isinstance(value, datetime):
            value = to_utc(value)
        setattr(task_db, key, value)

    db.commit()
    db.refresh(task_db)

    if mentions is not None:
        print("MENTIONS RICEVUTE")

        print(mentions)
        db.query(TaskMentions).filter(
            TaskMentions.task_id == id_task
        ).delete(synchronize_session=False)
       
        new_mentions = [
            TaskMentions(
                task_id=id_task,
                mentioned_user_id=m["mentioned_user_id"],
                created_by_user_id=m["created_by_user_id"],
                notification_read=m["notification_read"],
                created_at=m["created_at"]
            )
            for m in mentions
        ]
    
        db.add_all(new_mentions)
        db.commit()
    if manager.has_multiple_connections(current_user['id_utente']):
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
        if key == "priority" and value is not None:
            value = value.value
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
    if manager.has_multiple_connections(current_user['id_utente']):
        await manager.send_deleted_task_to_user(current_user['id_utente'],{"task_id": task_db.id_task ,"type": "deleted_task"})

    return {"msg":"Task eliminato"}
   

