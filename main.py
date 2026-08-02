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
from firebase import invia_push, invia_push_silenziosa
from fastapi.staticfiles import StaticFiles
import os




#todo se il server si spegne o ha un ionterruzzione deve ricalcolare tutte le date dei task

Base.metadata.create_all(bind=engine)

#manager = SocketManage()
from database import engine
from sqlalchemy import text



'''
def esegui_migrazione_sqlite():
    """
    Controlla se la colonna is_verified esiste. 
    Sblocca TUTTI gli utenti attuali impostandoli a 1 (True).
    """
    with engine.connect() as conn:
        try:
            # 1. Se la colonna non esiste, la crea impostando a 1 (True) i vecchi
            conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 1;"))
            conn.commit()
            print("🟢 Migrazione: Colonna creata e utenti impostati a True!")
        
        except Exception as e:
            # 2. Se la colonna esisteva già ma gli utenti erano rimasti bloccati a 0,
            # eseguiamo un UPDATE forzato una volta per tutte per sanare il database di test.
            try:
                conn.execute(text("UPDATE users SET is_verified = 1;"))
                conn.commit()
                print("🟢 Sanatoria database: Tutti gli utenti esistenti sono stati impostati a is_verified = True!")
            except Exception as update_err:
                print(f"❌ Errore durante l'update: {update_err}")
    
esegui_migrazione_sqlite()
'''




def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



from sqlalchemy import text
app = FastAPI()

# --- OPZIONE: Esecuzione automatica all'avvio del server ---
@app.on_event("startup")
def startup_migration():
    db = SessionLocal() # Crea una sessione manualmente
    try:
        queries = [
            "ALTER TABLE task_mentions ADD COLUMN notification_read BOOLEAN DEFAULT 0;",
            "ALTER TABLE task_mentions ADD COLUMN is_ui_deleted BOOLEAN DEFAULT 0;",
            "ALTER TABLE task_mentions ADD COLUMN read_at_time TIMESTAMP;",
            "ALTER TABLE task_mentions ADD COLUMN created_at TIMESTAMP;",
            "CREATE INDEX IF NOT EXISTS idx_task_mentions_notification_read ON task_mentions(notification_read);",
            "CREATE INDEX IF NOT EXISTS idx_task_mentions_is_ui_deleted ON task_mentions(is_ui_deleted);",
            "CREATE INDEX IF NOT EXISTS idx_task_mentions_mentioned_user_id ON task_mentions(mentioned_user_id);",
            "CREATE INDEX IF NOT EXISTS idx_task_mentions_created_by_user_id ON task_mentions(created_by_user_id);"
        ]
        
        for q in queries:
            try:
                db.execute(text(q))
                db.commit()
            except Exception:
                db.rollback() # Ignora l'errore se la colonna/indice esiste già
                
        print("Migrazione automatica completata con successo!")
    except Exception as e:
        print(f"Errore durante la migrazione: {e}")
    finally:
        db.close() # Chiude sempre la sessione

#app = FastAPI(lifespan=lifespan)



app.include_router(user)
app.include_router(task)

os.makedirs("/data/uploads", exist_ok=True)

os.makedirs("/data/uploads/profile", exist_ok=True)
app.mount(

    "/data/uploads",

    StaticFiles(directory="/data/uploads"),

    name="uploads"

)

#python-production-5e31.up.railway.app/tasks

@app.get("/tasks")

def debug_tasks(db: Session = Depends(get_db)):

    tasks = db.query(Task).all()

    return [

        {

            "id_task": t.id_task,

            "titolo": t.titolo,

            "user_id": t.user_id,

            "isDeleted": t.isDeleted,

            "datetime_task_last_update": t.datetime_task_last_update,
            "lastExpiredNotification": t.lastExpiredNotification,

            "completed": t.completato,

        }

        for t in tasks

    ]
    
import sqlite3

def _patch_task_71():
    try:
        conn = sqlite3.connect('/data/database.db')
        cursor = conn.cursor()
        
        # Aggiorna il task con id 71 (adatta i nomi delle colonne se necessario)
        cursor.execute("UPDATE tasks SET isDeleted = 1 WHERE id_task = 71")
        
        conn.commit()
        conn.close()
        print("-> [PATCH SERVER] Task 71 impostato con successo su isDeleted = 1")
    except Exception as e:
        print(f"-> [PATCH SERVER] Errore durante la correzione del task: {e}")

# Chiamalo all'avvio del server
#_patch_task_71()


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
   
@app.get("/debug/tokens")
def debug_tokens(db: Session = Depends(get_db)):
    return db.query(NotificationToken).all()

@app.get("/")
async def root():
    return RedirectResponse(

        url="https://todoregistrazione-production.up.railway.app/"

    )

from fastapi import UploadFile, File
import shutil

@app.post("/upload-db")
async def upload_db(file: UploadFile = File(...)):
    with open("/data/database.db", "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
   
    