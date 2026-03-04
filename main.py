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
from dateutil.relativedelta import relativedelta

from firebase import invia_push
# AGGIUNGERE ALLA TABELLA FINE RIPETIZIONE E LOGICA IN CONTROLLA TODO
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

def test(task: Task):
   
    
    task.task_datetime_repeat = task.task_datetime_repeat + timedelta(minutes=1)
 

def set_for_next_repeat_days(task: Task):
   
    task.task_datetime_repeat = task.task_datetime_repeat + timedelta(days=task.every)

def set_for_next_repeat_weeks(task: Task):
    task.task_datetime_repeat = task.task_datetime_repeat + timedelta(weeks=task.every)

def set_for_next_repeat_months(task: Task):
    task.task_datetime_repeat = task.task_datetime_repeat + relativedelta(months=task.every)


def set_for_next_repeat_years(task: Task):
    task.task_datetime_repeat = task.task_datetime_repeat + relativedelta(years=task.every)


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
                        print(f"Ripetizione ogni {task_all.every} Giorni --- prossima ripetizione {task_all.task_datetime_repeat} ")
                      
                   # if task_all.option == "Giorni":
                  #      print(f"Ripetizione ogni {task_all.every} Giorni")
                   #     if task_all.end_recurrency_time != None:
                    #        if task_all.end_recurrency_time == 0:
                     #           print("ripetizione == 0");
                      #      else:
                       #         task_all.end_recurrency_time -= 1   
                    if task_all.option == "Settimane":
                        print(f"Ripetizione ogni {task_all.every} Settimane")
                        
                    if task_all.option == "Mesi":
                         print(f"Ripetizione ogni {task_all.every} Mesi")
                    if task_all.option == "Anni":
                         print(f"Ripetizione ogni {task_all.every} Anni") 
                    

            print(f"{task_all.task_datetime_repeat} per l'id utente {task_all.user_id} Titolo: {task_all.titolo} ogni {task_all.every} numero ricorrenze {task_all.end_recurrency_time} ")
        db.commit()


    # todo gestire le ripetizioni per fine data e occorrenze
    db_results = db.query(Task).filter(Task.task_datetime_repeat <= now, Task.completato == False).all()
    if db_results:

        for todo in db_results:
            #user_token = db.query(NotificationToken).filter(NotificationToken.id_user_ref == todo.user_id).all()
           # if user_token:
            if todo.isRepeating == True:
                if todo.option == "Giorni":
                    print(f"Ripetizione ogni {todo.every}")
                    set_for_next_repeat_days(todo)
                    if todo.end_recurrency_time != None:
                        if todo.end_recurrency_time != 0:
                           todo.end_recurrency_time -=1
                           if todo.end_recurrency_time == 0:
                                   todo.completato = True
                                   print("\n\nEvento Completato\n\n")  

                # if todo.option == "Giorni":
                #    print(f"Ripetizione ogni {todo.every} Giorni")
                    #   set_for_next_repeat_days(todo)
                    
                if todo.option == "Settimane":
                    print(f"Ripetizione ogni {todo.every} Settimane")
                    set_for_next_repeat_weeks(todo)
                    if todo.end_recurrency_time != None:
                        if todo.end_recurrency_time != 0:
                           todo.end_recurrency_time -=1
                           if todo.end_recurrency_time == 0:
                                   todo.completato = True
                                   print("\n\nEvento Completato\n\n")  
                    
                if todo.option == "Mesi":
                        print(f"Ripetizione ogni {todo.every} Mesi")
                        set_for_next_repeat_months(todo)
                        if todo.end_recurrency_time != None:
                            if todo.end_recurrency_time != 0:
                                todo.end_recurrency_time -=1
                                if todo.end_recurrency_time == 0:
                                    todo.completato = True
                                    print("\n\nEvento Completato\n\n")  
                if todo.option == "Anni":
                        print(f"Ripetizione ogni {todo.every} Anni")  
                        set_for_next_repeat_years(todo)   
                        if todo.end_recurrency_time != None:
                            if todo.end_recurrency_time != 0:
                                todo.end_recurrency_time -=1
                                if todo.end_recurrency_time == 0:
                                   todo.completato = True
                                   print("\n\nEvento Completato\n\n")  
                    

              #  tokens = [ t.fcm_token for t in user_token ]
              #  invia_push(tokens,todo.titolo,todo.descrizione)
            if not todo.isRepeating:
                todo.completato = True
                print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")

          #  if not todo.isRepeating:
           #     todo.completato = True
            #    print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")
                #manda push notifiction a todo.user_id
        db.commit()

    db.close()

scheduler.add_job(controlla_todo, "interval", seconds=60)

app = FastAPI(lifespan=lifespan)


app.include_router(user)
app.include_router(task)



@app.get("/")
async def root():
    controlla_todo()
    return {"message": "Benvenuto!"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")