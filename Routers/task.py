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
from sqlalchemy import or_, and_
from firebase import invia_push, invia_push_silenziosa, invia_push_notifica,UnregisteredError       
from Models.models import User

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
                       datetime_task_last_update=datetime.now(timezone.utc), 
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
        sender = (
                db.query(User)
                .filter(User.id == current_user["id_utente"])
                .first()
            )
        
            
        for m in (task.mentions or []):
            if m.mentioned_user_id == current_user["id_utente"]:
                continue
            
            print(f"Utente {m.mentioned_user_id} menzionato")
            tokens = db.query(NotificationToken).filter(
            NotificationToken.id_user_ref == m.mentioned_user_id
            ).all()
        
            for token in tokens:
                try:
                   
                    invia_push_notifica(
                        token.fcm_token,
                        sender.nickname,
                        m.mentioned_user_id,
                        
                        "Nuova menzione",
                        f"{sender.nickname } ti ha menzionato in un task",
                        
                        "mention_created"
                    )
                except UnregisteredError:

                    db.query(NotificationToken).filter(

                        NotificationToken.fcm_token == token.fcm_token

                    ).delete()

                    db.commit()
            
                  
       
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
    lastSync: Optional[datetime] = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = (
        db.query(Task)
        .outerjoin(
            TaskMentions,
            Task.id_task == TaskMentions.task_id
        )
        .options(joinedload(Task.mentions))
        .filter(
            or_(
                Task.user_id == current_user["id_utente"],
                TaskMentions.mentioned_user_id == current_user["id_utente"],
            )
        )
    )

    # Se viene passata una data (anche quella del 2000 in caso di reset), filtriamo
    if lastSync is not None:
        query = query.filter(
            Task.datetime_task_last_update > lastSync
        )

    tasks = query.distinct().all()
    
    print("========== TASK RESTITUITI ==========")
    for t in tasks:
        print(
            f"TASK={t.id_task} "
            f"OWNER={t.user_id} "
            f"UPDATE={t.datetime_task_last_update} "
            f"MENTIONS={len(t.mentions)}"
        )

    return tasks

# todo provare per la modifica del singolo task se aggiorna datetime_task_last_update durante lo scarico degli aggiornamenti
@router.patch("/modifica_task")
async def modifica_task(id_task:int,task_update: UpdateTask, db = Depends(get_db), current_user = Depends(get_current_user)):

    print(f"accesso effettuato come {current_user['email']}")
    task_db = db.query(Task).filter(Task.id_task == id_task,Task.user_id == current_user['id_utente'], Task.isDeleted.is_(False)).first()
    if task_db is None:
        raise HTTPException(

            status_code=404,

            detail="Task non trovato"

        )

   # if task_update.isToUpdate:
    #    print("isToUpdate è vero, aggiorno data modifica")
    task_update.datetime_task_last_update = datetime.now(timezone.utc)
    #else:
     #   print("isToUpdate è false, non aggiorno data modifica")
    print(f"aggiornamento ore utc {datetime.now(timezone.utc)}")
    print(f"aggiornamento ore {datetime.now()}")

    update_data = task_update.model_dump(exclude_unset=True)
    print(update_data)
    print(update_data.get("datetime_task_last_update"))

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
        
        for m in new_mentions:

            if m.mentioned_user_id == current_user["id_utente"]:
                continue
            tokens = db.query(NotificationToken).filter(
                NotificationToken.id_user_ref == m.mentioned_user_id
                ).all()
            
            for token in tokens:
                try:
                    invia_push_silenziosa(
                        token.fcm_token,                    
                        "refresh"
                    )
                except UnregisteredError:

                    db.query(NotificationToken).filter(

                        NotificationToken.fcm_token == token.fcm_token

                    ).delete()

                    db.commit()

   
    
    return {

    "msg": "Valori Aggiornati",

    "datetime_task_last_update": task_db.datetime_task_last_update.isoformat()

}


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
#
    task_db.isDeleted = True
    task_db.datetime_task_last_update = datetime.now(timezone.utc)
    db.commit()
    
    mentions = (
    db.query(TaskMentions)
    .filter(TaskMentions.task_id == id_task)
    .all()
)
    
    sender = (
    db.query(User)
    .filter(User.id == current_user["id_utente"])
    .first()
)
    
    print("Prima della push")

    for mention in mentions:
        tokens = (
            db.query(NotificationToken)
            .filter(NotificationToken.id_user_ref == mention.mentioned_user_id)
            .all()
        )

        for token in tokens:
            print("Invio push a", token.fcm_token)
            try:
                invia_push_silenziosa(
                    token.fcm_token,
                    "mention_deleted",
                )
            except UnregisteredError:
                db.query(NotificationToken).filter(
                    NotificationToken.fcm_token == token.fcm_token
                ).delete()
                db.commit()

    print("Elimino task")
    
   #db.delete(task_db)

    
    print("Task flag impostato come eliminato")
    
    return {"msg":"Task eliminato","datetime_task_last_update": task_db.datetime_task_last_update}
   

