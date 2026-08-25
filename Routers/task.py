from typing import List
from datetime import timedelta, datetime
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
from firebase import invia_push, invia_push_silenziosa, invia_push_notifica, UnregisteredError       
from Models.models import User

router = APIRouter(prefix="/task", tags=["Task"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/ping")
def ping():
    return {"ok": 1}

def to_utc(dt: Optional[datetime]):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

@router.post("/crea_task", response_model=GetTask)
async def crea_task(task: CreaTask, db = Depends(get_db), current_user = Depends(get_current_user)):
    print(" CREA TASK CHIAMATA")
    print(f"accesso effettuato come {current_user['email']}")
    print(f"id  {current_user['id_utente']}")
    if not current_user['email'] or not current_user['id_utente']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    try:
        db_task = Task(
            titolo=task.titolo, 
            descrizione=task.descrizione if task.descrizione is not None else None, 
            creation_task_datetime=to_utc(task.creation_task_datetime), 
            datetime_task_last_update=datetime.now(timezone.utc), 
            all_day_datetime=task.all_day_datetime,
            is_all_day=task.is_all_day,
            task_datetime_repeat=(
                to_utc(task.task_datetime_repeat)
                if task.task_datetime_repeat
                else None
            ), 
            completato=task.completato,
            user_id=current_user['id_utente'],
            notificationEnabled=task.notificationEnabled,
            notify_before=task.notify_before,
            isRepeating=task.isRepeating, 
            priority=task.priority.value,
            every=task.every, 
            option=task.option,
            end_recurrency_time=task.end_recurrency_time,
            dateTime_task_end=to_utc(task.dateTime_task_end),
            category=task.category,
            location_name=task.location_name,
            longitude=task.longitude,
            latitude=task.latitude,
            share_position=task.share_position,
            share_acepted=task.share_acepted,
            isNearEnabled=task.isNearEnabled
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
                        f"{sender.nickname} ti ha menzionato in un task",
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


@router.get("/tutti_task", response_model=List[GetTask])
def visualizza_tasks(db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"accesso effettuato come {current_user['email']}")
    return db.query(Task).filter(Task.user_id == current_user['id_utente']).all()


@router.get("/tutti_task_filtered", response_model=List[GetTask])
def visualizza_tasks_filtered(
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

    if lastSync is not None:
        # --- BLOCCO DI DEBUG ---
        if lastSync.tzinfo is not None:
            lastSync = lastSync.replace(tzinfo=None)
        print(f"DEBUG lastSync ricevuto: {lastSync} (Tipo: {type(lastSync)})")
        
        latest_task = db.query(Task).order_by(Task.datetime_task_last_update.desc()).first()
        if latest_task:
            print(f"DEBUG Task più recente nel DB: {latest_task.datetime_task_last_update} (Tipo: {type(latest_task.datetime_task_last_update)})")
        else:
            print("DEBUG Nessun task trovato nel database.")
        # -----------------------

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


from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, Query


@router.get("/check_if_removed_mention", response_model=List[int])
def check_if_removed_mention(
    task_ids: List[int] = Query(default=[]),       
    lastSync: Optional[datetime] = None,         
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Costruiamo la dichiarazione con select() anziché db.query()
    stmt = (
        select(Task.id_task)
        .outerjoin(TaskMentions, Task.id_task == TaskMentions.task_id)
        .filter(
            or_(
                Task.user_id == current_user["id_utente"],
                TaskMentions.mentioned_user_id == current_user["id_utente"],
            )
        )
    )

    if task_ids:
        stmt = stmt.filter(Task.id_task.in_(task_ids))

    if lastSync is not None:
        if lastSync.tzinfo is not None:
            lastSync = lastSync.replace(tzinfo=None)
        stmt = stmt.filter(Task.datetime_task_last_update > lastSync)

    # Qui .scalars().all() funziona perfettamente perché execute() restituisce un Result
    task_ids_result = db.scalars(stmt.distinct()).all()
    
    print(f"========== ID TASK RESTITUITI: {task_ids_result} ==========")

    return task_ids_result


@router.patch("/modifica_task")
async def modifica_task(id_task: int, task_update: UpdateTask, db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"accesso effettuato come {current_user['email']}")
    
    task_db = db.query(Task).filter(Task.id_task == id_task, Task.user_id == current_user['id_utente']).first()
    if task_db is None:
        raise HTTPException(
            status_code=404,
            detail="Task non trovato"
        )

    # 🟢 AGGIORNIAMO SEMPRE LA DATA DI ULTIMA MODIFICA
    task_db.datetime_task_last_update = datetime.now(timezone.utc)

    update_data = task_update.model_dump(exclude_unset=True)
    mentions = update_data.pop("mentions", None)
    
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

    # Se ci sono modifiche alle menzioni, aggiorniamo le menzioni e forziamo di nuovo la data
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
        
        # 🟢 FORZIAMO L'AGGIORNAMENTO DELLA DATA ANCHE PER LE MENZIONI
        task_db.datetime_task_last_update = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(task_db)
        
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


@router.patch("/update_change_notify")
async def update_change_notify(id_task: int, task_update: UpdateTask, db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"accesso effettuato come {current_user['email']}")
    task_db = db.query(Task).filter(Task.id_task == id_task, Task.user_id == current_user['id_utente']).first()
    
    if task_db is None:
        raise HTTPException(status_code=404, detail="Task non trovato")

    task_db.datetime_task_last_update = datetime.now(timezone.utc)
    update_data = task_update.model_dump(exclude_unset=True)

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

    return {"msg": "Valori Aggiornati"}


@router.delete("/elimina_task/{id_task}")
async def elimina_task(id_task: int, db = Depends(get_db), current_user = Depends(get_current_user)):
    print(f"accesso effettuato come {current_user['email']}")
    print(f"id {current_user['id_utente']} task {id_task}")
    
    task_db = db.query(Task).filter(Task.id_task == id_task, Task.user_id == current_user['id_utente']).first()
    if not task_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task non trovato")

    task_db.isDeleted = True
    task_db.datetime_task_last_update = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task_db)
    
    mentions = (
        db.query(TaskMentions)
        .filter(TaskMentions.task_id == id_task)
        .all()
    )
    
    print("Prima della push di eliminazione")

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

    print("Task flag impostato come eliminato")
    
    return {
        "msg": "Task eliminato",
        "datetime_task_last_update": task_db.datetime_task_last_update.isoformat()
    }