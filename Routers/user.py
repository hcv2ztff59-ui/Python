from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy import or_, and_
from firebase import invia_push, invia_push_silenziosa, invia_push_notifica, UnregisteredError
import re
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse


from Auth.Auth import (
    crea_token, 
    crea_refresh_token, 
    hash_password_register, 
    verify_email_token,
    email_verification_token,
    hash_verify, 
    get_current_user, 
    verifica_refresh_token, 
    password_recovery_token,
    verify_reset_password
)
from Models.models import User, NotificationToken, Follow, TaskMentions, Task, SharedPosition
from Schemas.schemas import (
    SharedPositionCreate,   
    SharedPositionResponse,
    SharedPositionUpdate,
    AddFriendRequest,
    RegistraUtente,
    Login,
    TokenRequest,
    RefreshRequest,
    ModificaUtente,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    FollowResponse
)
from database import SessionLocal
from mail.mail import send_email

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/user", tags=["User"])


def _get_user_counts(user_id: int, db: Session):
    """Calcola in modo sincrono i contatori aggiornati per le push di un utente."""
    friend_requests = (
        db.query(Follow)
        .filter(Follow.followed_id == user_id, Follow.request_accepted == 0)
        .count()
    )
    mentions = (
        db.query(TaskMentions)
        .filter(TaskMentions.mentioned_user_id == user_id, TaskMentions.notification_read == 0)
        .count()
    )
    return {
        "unread_friends_count": str(friend_requests),
        "unread_mentions_count": str(mentions)
    }


@router.post("/login")
def login(user_in: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="l'utente non esiste")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email non verificata. Controlla la tua posta.")

    if not hash_verify(user_in.password, user.password):
        print(f"{user_in.password} - {user.password}")
        raise HTTPException(status_code=401, detail="Password non corretta")

    token = crea_token({"sub": user_in.email, "id": user.id})
    refresh_token = crea_refresh_token({"sub": user_in.email, "id": user.id})
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


@router.get("/get-users")
def get_users(query: str, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    followed_users = (
        db.query(Follow.followed_id)
        .filter(Follow.follower_id == current_user["id_utente"])
        .subquery()
    )

    users = db.query(User).filter(
        User.id != current_user["id_utente"],
        ~User.id.in_(followed_users),
        or_(
            User.nickname.ilike(f"%{query}%"),
            User.email.ilike(f"%{query}%"),
            User.nome_utente.ilike(f"%{query}%"),
        )
    ).limit(20).all()
    
    return [
        {
            "id_utente": user.id,
            "nome_utente": user.nome_utente,
            "email": user.email,
            "nickname": user.nickname,
            "image_profile": user.image_profile,
        }
        for user in users
    ]

@router.patch("/set-mention-read/{mention_id}")
def set_mention_read(
    mention_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mention = db.query(TaskMentions).filter(TaskMentions.id == mention_id).first()

    if not mention:
        raise HTTPException(status_code=404, detail="Menzione non trovata")

    # Modifica qui: usa current_user["id_utente"]
    if mention.created_by_user_id != current_user["id_utente"] and mention.mentioned_user_id != current_user["id_utente"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per modificare questa menzione")

    mention.read_at_time = datetime.now(timezone.utc)
    mention.notification_read = True
    db.commit()
    db.refresh(mention)
    
       # Determiniamo chi deve ricevere la notifica di ritorno (es. l'autore del task)
    target_user_id = (
        mention.created_by_user_id 
        if current_user["id_utente"] == mention.mentioned_user_id 
        else mention.mentioned_user_id
    )

    # Recuperiamo i token FCM dell'utente destinatario della ricevuta di lettura
    tokens = db.query(NotificationToken).filter(NotificationToken.id_user_ref == target_user_id).all()
    
    # Utente corrente che ha eseguito l'azione di lettura
    user = db.query(User).filter(User.id == current_user["id_utente"]).first()

    for token in tokens:
        try:
            invia_push_notifica(
                token.fcm_token,
                user.nickname,
                user.id,
                "Notifica di lettura",
                f"{user.nickname} ha letto la menzione",
                "notify_when_read",
            )
        except UnregisteredError:
            db.query(NotificationToken).filter(NotificationToken.fcm_token == token.fcm_token).delete()
            db.commit()

    return {
        "message": "Menzione impostata come letta con successo",
        "id": mention.id,
    }


@router.patch("/set-mention-deleted/{mention_id}")
def set_mention_deleted(
    mention_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mention = db.query(TaskMentions).filter(TaskMentions.id == mention_id).first()

    if not mention:
        raise HTTPException(status_code=404, detail="Menzione non trovata")

    # Modifica qui: usa current_user["id_utente"]
    if mention.created_by_user_id != current_user["id_utente"] and mention.mentioned_user_id != current_user["id_utente"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per eliminare questa menzione")

    mention.is_ui_deleted = True
    db.commit()
    db.refresh(mention)

    return {
        "message": "Menzione impostata come eliminata con successo",
        "mention_id": mention_id,
    }


@router.get("/get-all-mentions")
def get_all_mentions(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    # Recupera tutte le menzioni che coinvolgono l'utente corrente (come creatore o destinatario)
    # unendole con la tabella User per ricavare i dati del profilo
    mentions = (
        db.query(TaskMentions, User)
        .join(User, User.id == TaskMentions.mentioned_user_id)
        .filter(
            or_(
                TaskMentions.created_by_user_id == current_user["id_utente"],
                TaskMentions.mentioned_user_id == current_user["id_utente"]
            ),
        #TaskMentions.is_ui_deleted == False
        )
        .all()
    )


    return [
        {
            "id": mention.id,
            "task_id": mention.task_id,
            "mentioned_user_id": mention.mentioned_user_id,
            "created_by_user_id": mention.created_by_user_id,
            "nickname": user.nickname,
            "email": user.email,
            "name": user.nome_utente,
            "image_profile": user.image_profile,
            "notification_read": mention.notification_read,
            "is_ui_deleted": mention.is_ui_deleted,
            "read_at_time": mention.read_at_time,
            "created_at": mention.created_at,
            "is_shared_by_me": mention.created_by_user_id == current_user["id_utente"]
        }
        for mention, user in mentions
    ]

@router.patch("/set-all-mention-read")
def set_all_mentions_read(
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    mentions = (
        db.query(TaskMentions)
        .filter(
            or_(
                # Modifica qui: usa current_user["id_utente"]
                TaskMentions.created_by_user_id == current_user["id_utente"],
                TaskMentions.mentioned_user_id == current_user["id_utente"],
            ),
            TaskMentions.read_at_time == None,
        )
        .all()
    )

    if not mentions:
        raise HTTPException(
            status_code=404, detail="Nessuna menzione da aggiornare"
        )

    current_time = datetime.now(timezone.utc)
    for m in mentions:
        m.read_at_time = current_time
        m.notification_read = True

    db.commit()

    return {
        "message": "Tutte le menzioni sono state impostate come lette con successo",
        "updated_count": len(mentions),
    }


@router.get("/remove-friend")
def remove_friend(remove_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    follow = (
        db.query(Follow)
        .filter(
            Follow.request_accepted == True,
            or_(
                and_(Follow.follower_id == current_user["id_utente"], Follow.followed_id == remove_id),
                and_(Follow.follower_id == remove_id, Follow.followed_id == current_user["id_utente"]),
            )
        )
        .first()
    )

    if not follow:
        raise HTTPException(status_code=404, detail="Amico non trovato")

    db.delete(follow)
    db.commit()

    return {
        "success": True,
        "message": "Amico rimosso"
    }


@router.delete("/remove-mention")
def remove_mention(task_id: int, id_user_mentioned: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    print("REMOVE MENTION CHIAMATO")

    mentions = db.query(TaskMentions).filter(TaskMentions.task_id == task_id).all()
    if not mentions:
        raise HTTPException(status_code=404)

    is_creator = any(m.created_by_user_id == current_user["id_utente"] for m in mentions)
    
    if is_creator:
        mention = db.query(TaskMentions).filter(
            TaskMentions.task_id == task_id,
            TaskMentions.mentioned_user_id == id_user_mentioned,
        ).first()
    else:
        mention = db.query(TaskMentions).filter(
            TaskMentions.task_id == task_id,
            TaskMentions.mentioned_user_id == current_user["id_utente"],
        ).first()

    if not mention:
        raise HTTPException(status_code=404)

    task = db.query(Task).filter(Task.id_task == task_id).first()

    if task:
        user = db.query(User).filter(User.id == mention.mentioned_user_id).first()
        if user and user.nickname:
            task.titolo = task.titolo.replace(f"@{user.nickname}", "").replace("  ", " ").strip()
            task.titolo = re.sub(r"\s+", " ", task.titolo).strip()

    db.delete(mention)

    if task:
        task.datetime_task_last_update = datetime.now(timezone.utc)

    db.commit()

    if task:
        db.refresh(task)

    if task and task.user_id != current_user["id_utente"]:
        tokens = db.query(NotificationToken).filter(NotificationToken.id_user_ref == task.user_id).all()
        counts = _get_user_counts(task.user_id, db)

        for token in tokens:
            invia_push_silenziosa(
                token.fcm_token,
                "refresh",
                extra_data=counts
            )

    remaining_mentions = db.query(TaskMentions).filter(TaskMentions.task_id == task_id).all()

    for m in remaining_mentions:
        if m.mentioned_user_id == current_user["id_utente"]:
            continue

        tokens = db.query(NotificationToken).filter(NotificationToken.id_user_ref == m.mentioned_user_id).all()
        counts = _get_user_counts(m.mentioned_user_id, db)
        
        try:
            for token in tokens:
                invia_push_silenziosa(
                    token.fcm_token,
                    "refresh",
                    extra_data=counts
                )
        except UnregisteredError:
            db.query(NotificationToken).filter(NotificationToken.fcm_token == token.fcm_token).delete()
            db.commit()

    return {"success": True}


@router.get("/notifications-count")
def notifications_count(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    friend_requests = db.query(Follow).filter(Follow.followed_id == current_user["id_utente"], Follow.request_accepted == 0).count()
    mentions = db.query(TaskMentions).filter(TaskMentions.mentioned_user_id == current_user["id_utente"]).count()

    return {
        "count": friend_requests + mentions,
        "friend_requests": friend_requests,
        "mentions": mentions
    }


@router.get("/friend-requests-count")
def friend_requests_count(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    friend_requests = db.query(Follow).filter(Follow.followed_id == current_user["id_utente"], Follow.request_accepted == 0).count()
    return {"count": friend_requests}


@router.get("/mentions-unread-count")
def mentions_unread_count(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    mentions = db.query(TaskMentions).filter(TaskMentions.mentioned_user_id == current_user["id_utente"], TaskMentions.notification_read == 0).count()
    return {"count": mentions}


@router.get("/get-mentions")
def get_mentions(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    mentions = (
        db.query(TaskMentions, User)
        .join(User, User.id == TaskMentions.mentioned_user_id)
        .filter(or_(TaskMentions.created_by_user_id == current_user["id_utente"], TaskMentions.mentioned_user_id == current_user["id_utente"]))
        .all()
    )

    return [
        {
            "task_id": mention.task_id,
            "mentioned_user_id": mention.mentioned_user_id,
            "created_by_user_id": mention.created_by_user_id,
            "nickname": user.nickname,
            "email": user.email,
            "name": user.nome_utente,
            "image_profile": user.image_profile,
            "is_shared_by_me": mention.created_by_user_id == current_user["id_utente"]
        }
        for mention, user in mentions
    ]


@router.get("/friend-requests")
def friend_requests(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    users = (
        db.query(User, Follow.id)
        .join(Follow, User.id == Follow.follower_id)
        .filter(Follow.followed_id == current_user["id_utente"], Follow.request_accepted == False)
        .all()
    )
    
    return [
        {
            "follow_id": follow_id,
            "id_utente": user.id,
            "nome_utente": user.nome_utente,
            "nickname": user.nickname,
            "image_profile": user.image_profile,
        }
        for user, follow_id in users
    ]
    
    
@router.patch("/set-friend-request")
def set_friend_request(data: FollowResponse, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    follow = db.query(Follow).filter(Follow.id == data.follow_id).first()

    if not follow:
        raise HTTPException(status_code=404, detail="Richiesta non trovata")

    if follow.followed_id != current_user["id_utente"]:
        raise HTTPException(status_code=403, detail="Operazione non consentita")
        
    sender = db.query(User).filter(User.id == follow.follower_id).first()
    receiver = db.query(User).filter(User.id == follow.followed_id).first()
    
    if data.accepted:
        follow.request_accepted = True
        db.commit()

        tokens = db.query(NotificationToken).filter(NotificationToken.id_user_ref == sender.id).all()
        counts = _get_user_counts(sender.id, db)

        for token in tokens:
            try:
                invia_push_notifica(
                    token.fcm_token,
                    receiver.nickname,
                    receiver.id,
                    "Richiesta di amicizia",
                    f"{receiver.nickname} ha accettato la richiesta",
                    "friend_request",
                    extra_data=counts
                )
            except UnregisteredError:
                db.query(NotificationToken).filter(NotificationToken.fcm_token == token.fcm_token).delete()
                db.commit()

        return {"success": True}

    db.delete(follow)
    db.commit()
    return {"success": False}
    
    
@router.post("/add-friend")
def add_friend(data: AddFriendRequest, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    receiver = db.query(User).filter(User.id == data.followed_id).first()

    if not receiver:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    if data.followed_id == current_user["id_utente"]:
        raise HTTPException(status_code=400, detail="Non puoi seguire te stesso")

    existing = db.query(Follow).filter(
        or_(
            and_(Follow.follower_id == current_user["id_utente"], Follow.followed_id == data.followed_id),
            and_(Follow.follower_id == data.followed_id, Follow.followed_id == current_user["id_utente"]),
        )
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="Richiesta già esistente")

    follow = Follow(
        follower_id=current_user["id_utente"],
        followed_id=data.followed_id,
        created_at=datetime.now(timezone.utc)
    )

    db.add(follow)
    db.commit()

    sender = db.query(User).filter(User.id == current_user["id_utente"]).first()
    tokens = db.query(NotificationToken).filter(NotificationToken.id_user_ref == receiver.id).all()
    counts = _get_user_counts(receiver.id, db)

    for token in tokens:
        try:
            invia_push_notifica(
                token.fcm_token,
                sender.nickname,
                sender.id,
                "Nuova richiesta di amicizia",
                f"{sender.nickname} ti ha inviato una richiesta di amicizia",    
                "friend_request",
                extra_data=counts
            )
        except UnregisteredError:
            db.query(NotificationToken).filter(NotificationToken.fcm_token == token.fcm_token).delete()
            db.commit()

    return {
        "success": True,
        "nickname": receiver.nickname,
        "nome_utente": receiver.nome_utente,
        "image_profile": receiver.image_profile,
        "friend_id": receiver.id,
    }
    
    
@router.get("/get-friend")
def get_friend(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    users = (
        db.query(User)
        .join(
            Follow,
            or_(
                and_(Follow.follower_id == current_user["id_utente"], User.id == Follow.followed_id),
                and_(Follow.followed_id == current_user["id_utente"], User.id == Follow.follower_id),
            )
        )
        .filter(Follow.request_accepted == True)
        .all()
    )
   
    return [
        {
            "id_utente": user.id,
            "nome_utente": user.nome_utente,
            "email": user.email,
            "nickname": user.nickname,
            "image_profile": user.image_profile,
        }
        for user in users
    ]


@router.post("/refresh_token")
def refresh_token(data: RefreshRequest):
    return verifica_refresh_token(data.refresh_token)


@router.post("/register-token")
async def register_token(request: TokenRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    token = db.query(NotificationToken).filter(NotificationToken.fcm_token == request.fcm_token).first()

    if token:
        token.id_user_ref = current_user["id_utente"]
    else:
        token = NotificationToken(fcm_token=request.fcm_token, id_user_ref=current_user["id_utente"])
        db.add(token)

    db.commit()
    return {"message": "Token registrato"}


@router.post("/logout")
def logout(user: Login, db: Session = Depends(get_db)):
    pass


@router.get("/profile-image")
def get_profile_image(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["id_utente"]).first()
    if not user:
        raise HTTPException(status_code=404)

    image_name = user.image_profile
    if not image_name:
        raise HTTPException(status_code=404)

    image_path = Path("/data/uploads/profile") / image_name
    return FileResponse(image_path)


@router.post("/upload-profile-image")
async def upload_profile_image(image: UploadFile = File(...), current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["id_utente"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")


    # Nel metodo upload_profile_image cambia il percorso:
    os.makedirs("/data/uploads/profile", exist_ok=True)
    filename = f"profile_{user.id}.jpg"
    file_path = f"/data/uploads/profile/{filename}"
    

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    user.image_profile = filename
    user.updated_user_datetime = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return {
        "message": "Immagine caricata",
        "image_profile": filename,
        "updated_user_datetime": user.updated_user_datetime
    }


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if user:
        token = password_recovery_token(user.id)
        
        # 1. Il link nell'email DEVE essere un URL HTTP/HTTPS standard (sostituisci localhost con il tuo IP pubblico/dominio in produzione)
        reset_link = f"https://python-production-5e31.up.railway.app/user/reset-password?token={token}"
        
        send_email(
            email=user.email, 
            obj="Rigenera Password",
            body=f"""
            <h2>Recupero password</h2>
            <p>Hai richiesto il reset della password.</p>
            <p>Clicca sul pulsante qui sotto per reimpostarla direttamente nell'applicazione:</p>
            <p>
                <a href="{reset_link}" style="background-color: #007AFF; color: white; padding: 10px 20px; text-decoration: none; border-radius: 8px; display: inline-block;">
                    Reimposta Password
                </a>
            </p>
            <p>Se il pulsante non funziona, copia e incolla questo link nel browser:<br>{reset_link}</p>
            <p>Il link scadrà tra 1 ora.</p>
            """
        )
        
        print(reset_link)
        return {
            "success": True,
            "token": token
        }
    return {"success": False}


@router.get("/reset-password")
def verify_reset_link(token: str):
    # Verifichiamo se il token è valido ed estraiamo l'id utente
    user_id = verify_reset_password(token)
    
    if not user_id:
        raise HTTPException(status_code=400, detail="Token non valido o scaduto")

    # 2. Generiamo il Deep Link personalizzato che sveglierà l'app Flutter
    app_deep_link = f"pladdy://reset-password?token={token}"
    
    # 3. Reindirizziamo il browser verso l'app mobile
    return RedirectResponse(url=app_deep_link)

@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user_id = verify_reset_password(data.token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    user.password = hash_password_register(data.new_password)
    db.commit()
    return {"message": "Password aggiornata"}


@router.post("/register")
def register(user: RegistraUtente, db: Session = Depends(get_db)):
    db_query = db.query(User).filter(User.email == user.email).first()
    if not db_query:
        user = User(nome_utente=user.nome_utente, email=user.email, password=hash_password_register(user.password), nickname=user.nickname, is_verified = False)
        user.creation_user_datetime = datetime.now(timezone.utc)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = email_verification_token(user.id)
        
        verify_link = f"https://python-production-5e31.up.railway.app/user/verify-email?token={token}"
        
        send_email(email = user.email,
                   obj = "Attiva il tuo account Pladdy",
                   body=f"""
                    <h2>Benvenuto su Pladdy!</h2>
                    <p>Grazie per esserti registrato. Per favore, conferma la tua email cliccando qui sotto:</p>
                    <p><a href="{verify_link}" style="background-color: #007AFF; color: white; padding: 10px 20px; text-decoration: none; border-radius: 8px; display: inline-block;">Attiva Account</a></p>
                    """
                   )
        return {
            "message": "Utente creato, email di verifica inviata",
            "id": user.id
        }
        
    return {"message": "L'utente esiste già"}

@router.get("/verify-email")
def verify_email_link(token: str, db: Session = Depends(get_db)):
    user_id = verify_email_token(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Link scaduto o non valido")

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_verified = True  # 👈 L'utente ora è attivo!
        db.commit()

    # Reindirizza ad uno schema deep link speciale che dice a Flutter "attivazione completata!"
    return RedirectResponse(url="pladdy://email-verified")

@router.patch("/profile")
def save_edited_profile(data: ModificaUtente, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    user = db.query(User).filter(User.id == current_user["id_utente"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    user.updated_user_datetime = datetime.now(timezone.utc)
    if data.nome_utente is not None:
        user.nome_utente = data.nome_utente

    if data.nickname is not None and data.nickname != user.nickname:
        nickname_exists = db.query(User).filter(User.nickname == data.nickname, User.id != user.id).first()
        if nickname_exists:
            raise HTTPException(status_code=400, detail="Nickname già utilizzato")
        user.nickname = data.nickname

    if data.password is not None and data.password.strip() != "":
        user.password = hash_password_register(data.password)

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
def sync_edited_profile(data: ModificaUtente, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    user = db.query(User).filter(User.id == current_user["id_utente"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    user.updated_user_datetime = datetime.now(timezone.utc)
    if data.nome_utente is not None:
        user.nome_utente = data.nome_utente

    if data.nickname is not None and data.nickname != user.nickname:
        nickname_exists = db.query(User).filter(User.nickname == data.nickname, User.id != user.id).first()
        if nickname_exists:
            raise HTTPException(status_code=400, detail="Nickname già utilizzato")
        user.nickname = data.nickname

    db.commit()
    db.refresh(user)
    return {
        "message": "Utente modificato",
        "id": user.id,
        "nome_utente": user.nome_utente,
        "email": user.email,
        "nickname": user.nickname,
        "image_profile": user.image_profile,
        "updated_user_datetime": user.updated_user_datetime
    }
    
    
@router.delete("/delete-profile")
def delete_profile(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    user = db.query(User).filter(User.id == current_user["id_utente"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
        
    try:
        if user.image_profile:
            path = f"/data/uploads/profile/{user.image_profile}"
            if os.path.exists(path):
                os.remove(path)
        
        
        email_user = user.email
        
        db.query(Follow).filter((Follow.follower_id == user.id) | (Follow.followed_id == user.id)).delete(synchronize_session=False)
        db.query(TaskMentions).filter((TaskMentions.mentioned_user_id == user.id) | (TaskMentions.created_by_user_id == user.id)).delete(synchronize_session=False)
        db.query(Task).filter(Task.user_id == user.id).delete(synchronize_session=False)
        db.query(NotificationToken).filter(NotificationToken.id_user_ref == user.id).delete(synchronize_session=False)
        
        db.delete(user)
        db.commit()
        
        send_email(
            email=email_user, 
            obj="Cancellazione profilo",
            body=f"""
           <h2>Cancellazione Account Pladdy completata</h2>

            <p>Ciao,</p>

            <p>Ti confermiamo che il tuo account sull'app <strong>Pladdy</strong> è stato eliminato con successo, come da te richiesto.</p>

            <p>In conformità con le normative sulla privacy (GDPR), tutti i tuoi dati personali, i tuoi task, le tue menzioni e le tue relazioni di amicizia sono stati rimossi definitivamente dai nostri sistemi e non potranno più essere recuperati.</p>

            <p>Ci dispiace vederti andare via! Se in futuro vorrai tornare a organizzare i tuoi task con noi, la porta di Pladdy sarà sempre aperta.</p>

            <p>Grazie per aver fatto parte della nostra community.<br>
            <em>Il team di Pladdy</em></p>
            """
        )
        return {
            "success": True,
            "message": "Account eliminato"
        }
    except Exception:
        db.rollback()
        raise


@router.post("/create_shared_position", response_model=SharedPositionResponse, status_code=status.HTTP_201_CREATED)
def create_shared_position(
    position_in: SharedPositionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Utente che avvia la condivisione
):
    """
    Crea una nuova richiesta di condivisione posizione verso un altro utente.
    """
    db_position = SharedPosition(
        id_task_ref=position_in.id_task_ref,
        location_name=position_in.location_name,
        longitude=position_in.longitude,
        latitude=position_in.latitude,
        id_user_start=current_user["id_utente"], # Preso dal token di autenticazione
        id_user_end=position_in.id_user_end,
        share_accepted=False # Di default parte non accettato
    )
    
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position


@router.get("/get_user_shared_positions", response_model=List[SharedPositionResponse])
def get_user_shared_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Restituisce tutte le posizioni in cui l'utente corrente è coinvolto 
    (sia come mittente che come destinatario).
    """
    positions = db.query(SharedPosition).filter(
        (SharedPosition.id_user_start == current_user["id_utente"]) | 
        (SharedPosition.id_user_end == current_user["id_utente"])
    ).all()
    
    return positions


@router.patch("/accept_shared_position/{position_id}/accept", response_model=SharedPositionResponse)
def accept_shared_position(
    position_id: int,
    position_update: SharedPositionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Permette all'utente destinatario (id_user_end) di accettare o rifiutare la condivisione.
    """
    db_position = db.query(SharedPosition).filter(SharedPosition.id == position_id).first()
    
    if not db_position:
        raise HTTPException(status_code=404, detail="Condivisione posizione non trovata.")
    
    # Verifica che sia proprio l'utente destinatario a poter accettare
    if db_position.id_user_end != current_user["id_utente"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Non hai i permessi per modificare questa condivisione."
        )
    
    db_position.share_accepted = position_update.share_accepted
    db.commit()
    db.refresh(db_position)
    
    return db_position


