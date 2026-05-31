from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from Auth.Auth import crea_token, crea_refresh_token, hash_password_register, hash_verify, get_current_user, verifica_refresh_token
from Models.models import User, NotificationToken
from Schemas.schemas import RegistraUtente, Login, TokenRequest, RefreshRequest, ModificaUtente
from database import SessionLocal
from fastapi import UploadFile,File
import shutil
import os
from pathlib import Path
from fastapi.responses import FileResponse

from datetime import datetime, timezone

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
router = APIRouter(prefix="/user", tags=["User"])

@router.post("/login")
def login(user_in:Login, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == user_in.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="l'utente non esiste")

    if not hash_verify(user_in.password, user.password):
        print(f"{user_in.password} - {user.password}")
        raise HTTPException(status_code=401, detail="Password non corretta")

    token = crea_token({"sub":user_in.email,"id":user.id})
    refresh_token = crea_refresh_token({"sub":user_in.email,"id":user.id})
    return {
        "name": user.nome_utente,
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "image_profile": user.image_profile,
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.get("/get_user_info")
def get_user_info(current_user = Depends(get_current_user), db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == current_user.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="l'utente non esiste")
    
    return {
        "name": user.nome_utente,
        "id_utente": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "image_profile": user.image_profile,
        
    }


@router.post("/refresh_token")
def refresh_token(data: RefreshRequest):
   return verifica_refresh_token(data.refresh_token)

# endpoint per token notifiche push
@router.post("/register-token")
async def register_token(
        request: TokenRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # 1. Controlliamo se il token esiste già nel DB
    existing_token = db.query(NotificationToken).filter(
        NotificationToken.fcm_token == request.fcm_token
    ).first()

    if existing_token:
        # Se esiste già ma è di un altro utente (raro ma possibile), lo aggiorniamo
        existing_token.id_user_ref = current_user['id_utente']
        db.commit()
        return {"message": "Token aggiornato"}

    # 2. Se non esiste, creiamo un nuovo record
    new_token = NotificationToken(
        fcm_token=request.fcm_token,
        id_user_ref=current_user['id_utente']
    )

    try:
        db.add(new_token)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante il salvataggio del token")

    return {"message": "Token registrato con successo"}

@router.post("/logout")
def logout(user:Login, db: Session = Depends(get_db)):
    pass



@router.get("/profile-image")

def get_profile_image(current_user=Depends(get_current_user),db: Session = Depends(get_db)):

    user = db.query(User).filter(User.id == current_user["id_utente"]).first()

    if not user:

        raise HTTPException(status_code=404)

    image_name = user.image_profile

    if not image_name:

        raise HTTPException(status_code=404)

    image_path = Path("uploads/profile") / image_name

    return FileResponse(image_path)

@router.post("/upload-profile-image")
async def upload_profile_image(
    image: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)):

    user = db.query(User).filter(

        User.id == current_user["id_utente"]

    ).first()

    if not user:

        raise HTTPException(

            status_code=404,

            detail="Utente non trovato"

        )

    os.makedirs("uploads/profile", exist_ok=True)

    filename = f"profile_{user.id}.jpg"

    file_path = f"uploads/profile/{filename}"

    with open(file_path, "wb") as buffer:

        shutil.copyfileobj(image.file, buffer)

    user.image_profile = filename

    db.commit()

    return {
        "message": "Immagine caricata",
        "image_profile": file_path

    }

@router.post("/register")
def register(user:RegistraUtente, db: Session = Depends(get_db)):
    db_query = db.query(User).filter(User.email == user.email).first()
    print(f"Lunghezza in caratteri: {len(user.password)}")
    print(f"Lunghezza in byte: {len(user.password.encode('utf-8'))}")
    if not db_query:
        user = User(nome_utente = user.nome_utente, email = user.email, password = hash_password_register(user.password),nickname = user.nickname )
        
        user.creation_user_datetime =  datetime.now(timezone.utc)
        db.add(user)
        db.commit()
        db.refresh(user)
        return {
            "message": "Utente creato",
            "id": user.id
            }


    return {"message": "Utente già esistente"}

@router.patch("/profile")
def save_edited_profile(
    data: ModificaUtente,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    user = db.query(User).filter(
        User.id == current_user["id_utente"]
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Utente non trovato"
        )

    user.updated_user_datetime =  datetime.now(timezone.utc)
    # Nome
    if data.nome_utente is not None:
        user.nome_utente = data.nome_utente

    # Nickname
    if data.nickname is not None and data.nickname != user.nickname:

        nickname_exists = db.query(User).filter(
            User.nickname == data.nickname,
            User.id != user.id
        ).first()

        if nickname_exists:
            raise HTTPException(
                status_code=400,
                detail="Nickname già utilizzato"
            )

        user.nickname = data.nickname

    # Password
    if data.password is not None and data.password.strip() != "":
        user.password = hash_password_register(
            data.password
        )

    db.commit()
    db.refresh(user)

    return {
        "message": "Utente modificato",
        "id": user.id,
        "nome_utente": user.nome_utente,
        "email": user.email,
        "nickname": user.nickname,
        "image_profile": user.image_profile
    }
    
@router.patch("/profile-sync")
def sync_edited_profile(
    data: ModificaUtente,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    user = db.query(User).filter(
        User.id == current_user["id_utente"]
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Utente non trovato"
        )

    user.updated_user_datetime =  datetime.now(timezone.utc)
    # Nome
    if data.nome_utente is not None:
        user.nome_utente = data.nome_utente

    # Nickname
    if data.nickname is not None and data.nickname != user.nickname:

        nickname_exists = db.query(User).filter(
            User.nickname == data.nickname,
            User.id != user.id
        ).first()

        if nickname_exists:
            raise HTTPException(
                status_code=400,
                detail="Nickname già utilizzato"
            )

        user.nickname = data.nickname

    

    db.commit()
    db.refresh(user)

    return {
        "message": "Utente modificato",
        "id": user.id,
        "nome_utente": user.nome_utente,
        "email": user.email,
        "nickname": user.nickname,
        "image_profile": user.image_profile
    }
