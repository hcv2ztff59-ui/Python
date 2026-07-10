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

def esegui_migrazione_sqlite():
    """
    Controlla se la colonna is_verified esiste. 
    Se manca, la crea e imposta TUTTI i vecchi utenti esistenti a TRUE (1) solo la prima volta.
    """
    with engine.connect() as conn:
        try:
            # 1. Proviamo ad aggiungere la colonna impostando il DEFAULT a 1 (True).
            # In questo modo, SQLite prenderà tutti i vecchi record esistenti e scriverà 1 in automatico! ok
            conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 1;"))
            conn.commit()
            print("🟢 Migrazione iniziale completata: Vecchi utenti impostati a is_verified = True!")
        
        except Exception as e:
            # 2. Se entra qui, significa che la colonna esiste già dai deploy precedenti.
            # Non dobbiamo fare più nulla perché i vecchi utenti sono già stati sanati la prima volta,
            # e i nuovi utenti registrati da ora in poi nasceranno con is_verified = False (0) dal modello SQLAlchemy.
            print("ℹ️ Struttura database già aggiornata. Nessuna azione sui vecchi utenti.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




#app = FastAPI(lifespan=lifespan)
app = FastAPI()


app.include_router(user)
app.include_router(task)

os.makedirs("uploads", exist_ok=True)

os.makedirs("uploads/profile", exist_ok=True)
app.mount(

    "/uploads",

    StaticFiles(directory="uploads"),

    name="uploads"

)

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
   
    