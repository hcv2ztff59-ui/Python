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
from fastapi.responses import RedirectResponse
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

#scheduler = AsyncIOScheduler()
'''
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not scheduler.running:
        scheduler.add_job(controlla_todo, "interval", seconds=30)
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
    #SE HO UN NUMERO DI RICORRENZE 
    if task.end_recurrency_time != None:
        if datetime.now() >= task.task_datetime_repeat:
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

    #SE HO UNA DATA DI FINE RICORRENZA
    if task.dateTime_task_end != None:
        if datetime.now() >=task.dateTime_task_end:
            return True
    return False

# no async perchè se è terminato lo devo sapere subito
def isEndTask(todo: Task, now: datetime) -> bool:

    if todo.end_recurrency_time is None:
        return False
    #ottengo ad esempio 7(minuti)
    end = todo.every * todo.end_recurrency_time
    #sommo i 7 minuti alla data attuale
    #actual recurrency = 2026-03-28 15:11:16.118475+00:00(data end) 2026-03-28 15:03:16.115817+00:00

    #todo gestire il calcolo in gg, settimane, mesi , anni
    end_task = todo.task_datetime_repeat + timedelta(days = end)
    print(f"actual recurrency = {end_task} {now}")
    if now  > end_task :
        print("Task Scaduto - Lo salto e lo segno come completato")
        todo.completato = True
        return True
    return False
    #mettere calcolo riccorrenze rimanenti in caso di caduta server 


def to_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)  # ok se sai che è UTC
    return dt.astimezone(timezone.utc)

async def check_task(todo,now):
        safety_iter = 100
        task_date = todo.task_datetime_repeat

       # if task_date.tzinfo is None:
        #    task_date = task_date.replace(tzinfo=timezone.utc)
        #user_token = db.query(NotificationToken).filter(NotificationToken.id_user_ref == todo.user_id).all()
           # if user_token:
        if todo.isRepeating == True:
         
            while task_date <= now and safety_iter > 0:
                safety_iter -= 1
                print("Task Scaduto - Lo aggiorno per la prossima occorrenza")
                if todo.option == "Giorni":
                    print(f"E una Ripetizione ogni {todo.every}\n")
                    #await test(todo)
                    await set_for_next_repeat_days(todo)

                elif todo.option == "Settimane":
                    print(f"Ripetizione ogni {todo.every} Settimane")
                    await set_for_next_repeat_weeks(todo)
                               
                elif todo.option == "Mesi":
                    print(f"Ripetizione ogni {todo.every} Mesi")
                    await set_for_next_repeat_months(todo)
          
                elif todo.option == "Anni":
                    print(f"Ripetizione ogni {todo.every} Anni")  
                    await set_for_next_repeat_years(todo)   
     
                if await check_recurrency_end_task(todo):
                    print("\n\nCOMPLETATO == TRUE!!!!!!\n\n")
                    todo.completato = True
                    break
                else:
                    print(f"Task {todo.titolo} notifica , nuova data di ripetizione {todo.task_datetime_repeat}")
                #assegno prossima data di ripetizione se in ritardo
                task_date = todo.task_datetime_repeat
                print(f"Task {todo.id_task} è scaduto, nuova data di ripetizione {task_date}")
                        
        else:
            todo.completato = True      

            #  tokens = [ t.fcm_token for t in user_token ]
            #  invia_push(tokens,todo.titolo,todo.descrizione)
        if todo.completato:
            await manager.send_complete_task_to_user(todo.user_id,{"task_id":todo.id_task, "type": "complete_task", "completato": todo.completato})
            print(f"il Task {todo.id_task} dell'utente {todo.user_id} è completato")

     

async def controlla_todo() :
    db = SessionLocal()

    #now = datetime.now(timezone.utc)
    now = datetime.utcnow()
    try:
        # TODO CHECK RICORRENZE PERCHE NE PRENDE PIU DI UNA E ANCHE A DATA SBAGLIATA
     
        task_incoming = db.query(Task).filter(Task.task_datetime_repeat <= now, Task.completato == False).order_by(asc(Task.task_datetime_repeat)).all()
    
        for task_all in task_incoming:
            # Se è scaduto il task, lo segno come completato e passo al prossimo
            # todo spostare questo controllo quando parte il server
            if isEndTask(task_all,now):
                continue
            await check_task(task_all,now)        
        
        db.commit()
    finally:
        db.close()
    

'''


#app = FastAPI(lifespan=lifespan)
app = FastAPI()


app.include_router(user)
app.include_router(task)


@app.websocket("/ws")
async def socket_endpoint(websocket: WebSocket):
    
    token = websocket.query_params.get("token")  or websocket.query_params.get("access_token")

    if not token:

        print("❌ TOKEN MANCANTE")

        await websocket.close(code=1008)

        return
    
    user = get_current_user_web_socket(token)

    user_id = user["id_utente"]
    
    await manager.connect(user_id, websocket)

    print("🟢 CONNECT", user_id, websocket)
    print(f"Connessioni attive per {user_id}: {len(manager.active_connections.get(user_id, []))}")

    try:
        while True:
            # serve solo per mantenere viva la connessione
            await websocket.receive_text()
           
    except WebSocketDisconnect:
        print("🔴 disconnesso", user_id)
        manager.disconnect(user_id, websocket)

    except Exception as e:
        print("🔴 errore ws:", e)
        manager.disconnect(user_id, websocket)
   


@app.get("/")
async def root():
    return RedirectResponse(

        url="https://todoregistrazione-production.up.railway.app/"

    )



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
    