import asyncio
from contextlib import asynccontextmanager
import firebase
from Service.Socket import SocketManage, manager
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from Auth.Auth import get_current_user
from Models.models import Task, NotificationToken
from Routers.user import router as user
from Routers.task import router as task
from database import Base, engine, SessionLocal
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from Auth.Auth import get_current_user_web_socket
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import desc,asc

from firebase import invia_push


#todo se il server si spegne o ha un ionterruzzione deve ricalcolare tutte le date dei task

Base.metadata.create_all(bind=engine)

#manager = SocketManage()



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()

async def test(task: Task):
    #era 2 minuti
    task.task_datetime_repeat = task.task_datetime_repeat + timedelta(minutes=1)
   
 

async def set_for_next_repeat_days(task: Task):
   
    task.task_datetime_repeat = task.task_datetime_repeat + timedelta(days=task.every)

async def set_for_next_repeat_weeks(task: Task):
    task.task_datetime_repeat = task.task_datetime_repeat + timedelta(weeks=task.every)

async def set_for_next_repeat_months(task: Task):
    task.task_datetime_repeat = task.task_datetime_repeat + relativedelta(months=task.every)


async def set_for_next_repeat_years(task: Task):
    task.task_datetime_repeat = task.task_datetime_repeat + relativedelta(years=task.every)

async def check_recurrency_end_task(task: Task) -> bool:
    print(f"---------------------------- >ricorrenza {task.end_recurrency_time }")
    if task.end_recurrency_time != None:
        task.end_recurrency_time -=1
        await manager.send_occurrency_update_to_user(task.user_id,{
                            "task_id": task.id_task,
                            "type": "occurrency",
                            "date_time_repeat": task.task_datetime_repeat,
                            "end_recurrency_time": task.end_recurrency_time})    
        
        if task.end_recurrency_time == 0:
            return True
        else: 
            return False


    if task.dateTime_task_end != None:
        if task.end_recurrency_time == datetime.now():
            return True
    return False

# no async perchè se è terminato lo devo sapere subito
def isEndTask(todo: Task, now: datetime):
    #ottengo ad esempio 7(minuti)
    end = todo.every * todo.end_recurrency_time
    #sommo i 7 minuti alla data attuale
    #actual recurrency = 2026-03-28 15:11:16.118475+00:00(data end) 2026-03-28 15:03:16.115817+00:00
    end_task = datetime.now(timezone.utc) + timedelta(minutes = end)
    print(f"actual recurrency = {end_task} {now}")
    if now  > end_task :
        print("Task Scaduto")
        todo.completato = True
    #mettere calcolo riccorrenze rimanenti in caso di caduta server 

async def check_task(todo,now):
        max_iter = 100  # safety
        task_date = todo.task_datetime_repeat

        if task_date.tzinfo is None:
            task_date = task_date.replace(tzinfo=timezone.utc)
      #user_token = db.query(NotificationToken).filter(NotificationToken.id_user_ref == todo.user_id).all()
           # if user_token:
        if todo.isRepeating == True:
            if task_date <= now and max_iter > 0:
                max_iter -= 1
                if todo.option == "Giorni":
                    print(f"E una Ripetizione ogni {todo.every}\n")
                    await test(todo)
                    #set_for_next_repeat_days(todo)
                    # print(f"CHECK {check_recurrency_end_task(todo)}");
                    if await check_recurrency_end_task(todo):
                        print("\n\nCOMPLETATO == TRUE!!!!!!\n\n")
                        todo.completato = True
                        
               #         await manager.send_complete_task_to_user(todo.user_id,{"task_id":todo.id_task, "type": "complete_task", "completato": todo.completato})
                    else:
                        print("Ricorrenza scalata\n")
                if todo.option == "Settimane":
                    print(f"Ripetizione ogni {todo.every} Settimane")
                    await set_for_next_repeat_weeks(todo)
                    if await check_recurrency_end_task(todo):
                        todo.completato = True
                        
                    
                if todo.option == "Mesi":
                    print(f"Ripetizione ogni {todo.every} Mesi")
                    await set_for_next_repeat_months(todo)
                    if await check_recurrency_end_task(todo):
                        todo.completato = True
                        

                if todo.option == "Anni":
                    print(f"Ripetizione ogni {todo.every} Anni")  
                    await set_for_next_repeat_years(todo)   
                    if await check_recurrency_end_task(todo):
                        todo.completato = True 
                        
        else:
            todo.completato = True      

            #  tokens = [ t.fcm_token for t in user_token ]
            #  invia_push(tokens,todo.titolo,todo.descrizione)
        if todo.completato:
            await manager.send_complete_task_to_user(todo.user_id,{"task_id":todo.id_task, "type": "complete_task", "completato": todo.completato})
            print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")

        # if not todo.isRepeating:
        #    todo.completato = True
            #   print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")

        #  if not todo.isRepeating:
        #     todo.completato = True
        #    print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")
            #manda push notifiction a todo.user_id
        

async def controlla_todo() :
    db = SessionLocal()

    now = datetime.now(timezone.utc)
   
    try:
        # TODO CHECK RICORRENZE PERCHE NE PRENDE PIU DI UNA E ANCHE A DATA SBAGLIATA
        #db_results = db.query(Task).filter(Task.task_datetime_repeat <= now, Task.completato == False).all()
        #print(f"Lista:\n")
        db_past = db.query(Task).filter(Task.task_datetime_repeat < now, Task.completato == False).order_by(asc(Task.task_datetime_repeat)).all()

        db_future = db.query(Task).filter(Task.task_datetime_repeat <= now, Task.completato == False).order_by(asc(Task.task_datetime_repeat)).all()
    
        for task_all in db_future:
            isEndTask(task_all,now)
            await check_task(task_all,now)        
        
        db.commit()
    finally:
        db.close()
    
'''
   
    if db_results:

        for todo in db_results:
            #user_token = db.query(NotificationToken).filter(NotificationToken.id_user_ref == todo.user_id).all()
           # if user_token:
            if todo.isRepeating == True:
                if todo.option == "Giorni":
                    print(f"E una Ripetizione ogni {todo.every}\n")
                    await test(todo)
                    #set_for_next_repeat_days(todo)
                   # print(f"CHECK {check_recurrency_end_task(todo)}");
                    if await check_recurrency_end_task(todo):
                        print("\n\nCOMPLETATO == TRUE!!!!!!\n\n")
                        todo.completato = True
                        await manager.send_complete_task_to_user(todo.user_id,{"task_id":todo.id_task, "type": "complete_task", "completato": todo.completato})
                    else:
                        print("Ricorrenza scalata\n")
                if todo.option == "Settimane":
                    print(f"Ripetizione ogni {todo.every} Settimane")
                    set_for_next_repeat_weeks(todo)
                    if await check_recurrency_end_task(todo):
                        todo.completato = True
                    
                if todo.option == "Mesi":
                        print(f"Ripetizione ogni {todo.every} Mesi")
                        set_for_next_repeat_months(todo)
                        if await check_recurrency_end_task(todo):
                            todo.completato = True

                if todo.option == "Anni":
                        print(f"Ripetizione ogni {todo.every} Anni")  
                        set_for_next_repeat_years(todo)   
                        if await check_recurrency_end_task(todo):
                            todo.completato = True 
            else:
                todo.completato = True      

              #  tokens = [ t.fcm_token for t in user_token ]
              #  invia_push(tokens,todo.titolo,todo.descrizione)
            if todo.completato:
               await manager.send_complete_task_to_user(todo.user_id,{"task_id":todo.id_task, "type": "complete_task", "completato": todo.completato})
               print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")

           # if not todo.isRepeating:
            #    todo.completato = True
             #   print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")

          #  if not todo.isRepeating:
           #     todo.completato = True
            #    print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")
                #manda push notifiction a todo.user_id
        db.commit()


        

    print("******* STAMPA ********")
    db_await_result = db.query(Task).filter(Task.task_datetime_repeat >= now, Task.completato == False).all()
    if db_await_result:
        print(f"Prossimi eventi:\n")
        for task_all in db_await_result:
             

             #todo continuare qua deve calcolare il prossimo evento 
            if task_all.isRepeating == True:
                    if task_all.option == "Giorni":
                        print(f"Ripetizione ogni {task_all.every} Giorni --- prossima ripetizione {task_all.task_datetime_repeat} ")  
                        if task_all.end_recurrency_time != None:
                            if task_all.end_recurrency_time == 0:
                                print("\tFine Ripetizione - Task Completato :) ");
                            else:
                                print(f"\tMancano {task_all.end_recurrency_time} ricorrenze :) ");
                        if task_all.dateTime_task_end != None:
                            if task_all.dateTime_task_end != datetime.now():
                                    print(f"\Data fine Evento {task_all.dateTime_task_end} :) ");
                            else:
                                print(f"\tFine Task  :) ");

                     
                    if task_all.option == "Settimane":
                        print(f"Ripetizione ogni {task_all.every} Settimane")
                        
                    if task_all.option == "Mesi":
                         print(f"Ripetizione ogni {task_all.every} Mesi")
                    if task_all.option == "Anni":
                         print(f"Ripetizione ogni {task_all.every} Anni") 
            else:
                print(f"\n----> Titolo: {task_all.titolo}{task_all.descrizione} data fine {task_all.dateTime_task_end} \n")         
            if(task_all.end_recurrency_time != None):
             print(f"\n---->{task_all.task_datetime_repeat} per l'id utente {task_all.user_id} Titolo: {task_all.titolo}{task_all.descrizione}  ogni {task_all.every} minuti\nnumero ricorrenze {task_all.end_recurrency_time}\ndata fine {task_all.dateTime_task_end} \n")
        db.commit()
    db.close()
    print("***************")'''

scheduler.add_job(controlla_todo, "interval", seconds=30)

app = FastAPI(lifespan=lifespan)


app.include_router(user)
app.include_router(task)


@app.websocket("/ws")
async def socket_endpoint(websocket: WebSocket):
    
    token = websocket.query_params.get("token")
    user = get_current_user_web_socket(token)
    
    if user is None:
        await websocket.close()
        return

    user_id = user["id_utente"]
    
    await manager.connect(user_id, websocket)

    try:
        while True:
            # serve solo per mantenere viva la connessione
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
            # nessun messaggio → ok, continua
                pass
    except WebSocketDisconnect:
        print("🔴 disconnesso", user_id)
        manager.disconnect(user_id, websocket)

    except Exception as e:
        print("🔴 errore ws:", e)
        manager.disconnect(user_id, websocket)
   


@app.get("/")
async def root():
    await controlla_todo()
    return {"message": "Benvenuto!"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )