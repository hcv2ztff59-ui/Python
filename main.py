from contextlib import asynccontextmanager
import firebase
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from Auth.Auth import get_current_user
from Models.models import Task, NotificationToken
from Routers.user import router as user
from Routers.task import router as task
from database import Base, engine, SessionLocal
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone, timedelta

from firebase import invia_push

#TODO MODIFICARE  FUNC PER  RIPETIZIONE
# CREA TABELLE
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()

def set_for_next_repeat_days(task: Task):
   
    task.task_datetime_repeat = task.task_datetime_repeat + timedelta(days=task.every)

    
    


def set_for_next_repeat_weeks(task: Task):
    task.task_datetime_repeat = task.task_datetime_repeat + timedelta(week=task.every)

def set_for_next_repeat_months(task: Task):
    pass

def set_for_next_repeat_years(task: Task):
    pass

def controlla_todo():
    db = SessionLocal()

    now = datetime.now()
    # formato datetime 2026-01-23T10:30:00
    #filtro
    prossima_ora = now + timedelta(hours=1)
    db_await_result = db.query(Task).filter(Task.task_datetime_repeat > now, Task.completato == False).all()
    if db_await_result:
        print(f"Prossimi eventi:\n")
        for task_all in db_await_result:
             

             #todo continuare qua deve calcolare il prossimo evento 
            if task_all.isRepeating == True:
                    if task_all.option == "Giorni":
                        print(f"Ripetizione ogni {task_all.every} Giorni")
                        
                    if task_all.option == "Settimane":
                        print(f"Ripetizione ogni {task_all.every} Settimane")
                        
                    if task_all.option == "Mesi":
                         print(f"Ripetizione ogni {task_all.every} Mesi")
                    if task_all.option == "Anni":
                         print(f"Ripetizione ogni {task_all.every} Anni") 

            print(f"{task_all.task_datetime_repeat} per l'id utente {task_all.user_id} Titolo: {task_all.titolo}")
        db.commit()


    db_results = db.query(Task).filter(Task.task_datetime_repeat <= now, Task.completato == False).all()
    if db_results:

        for todo in db_results:
            user_token = db.query(NotificationToken).filter(NotificationToken.id_user_ref == todo.user_id).all()
            if user_token:
                if todo.isRepeating == True:
                    if todo.option == "Giorni":
                        print(f"Ripetizione ogni {todo.every} Giorni")
                        set_for_next_repeat_days(todo)
                        
                    if todo.option == "Settimane":
                        print(f"Ripetizione ogni {todo.every} Settimane")
                        set_for_next_repeat_weeks(todo)
                        
                    if todo.option == "Mesi":
                         print(f"Ripetizione ogni {todo.every} Mesi")
                    if todo.option == "Anni":
                         print(f"Ripetizione ogni {todo.every} Anni")            

                tokens = [ t.fcm_token for t in user_token ]
                invia_push(tokens,todo.titolo,todo.descrizione)
                if not todo.isRepeating:
                    todo.completato = True
                print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")

            if not todo.isRepeating:
                todo.completato = True
            print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")
            #manda push notifiction a todo.user_id
        db.commit()

    db.close()

scheduler.add_job(controlla_todo, "interval", seconds=90)

app = FastAPI(lifespan=lifespan)


app.include_router(user)
app.include_router(task)



@app.get("/")
async def root():
    controlla_todo()
    return {"message": "Benvenuto!"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")