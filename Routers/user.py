from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from Auth.Auth import crea_token, crea_refresh_token, hash_password_register, hash_verify, get_current_user, verifica_refresh_token
from Models.models import User, NotificationToken
from Schemas.schemas import RegistraUtente, Login, TokenRequest, RefreshRequest
from database import SessionLocal


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
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
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

@router.post("/register")
def register(user:RegistraUtente, db: Session = Depends(get_db)):
    db_query = db.query(User).filter(User.email == user.email).first()
    print(f"Lunghezza in caratteri: {len(user.password)}")
    print(f"Lunghezza in byte: {len(user.password.encode('utf-8'))}")
    if not db_query:
        user = User(nome_utente = user.nome_utente, email = user.email, password = hash_password_register(user.password) )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"message": "Utente creato"}


    return {"message": "Utente già esistente"}
