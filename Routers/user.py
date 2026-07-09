from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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

from Auth.Auth import (
    crea_token, 
    crea_refresh_token, 
    hash_password_register, 
    hash_verify, 
    get_current_user, 
    verifica_refresh_token, 
    password_recovery_token,
    verify_reset_password
)
from Models.models import User, NotificationToken, Follow, TaskMentions, Task
from Schemas.schemas import (
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

    image_path = Path("uploads/profile") / image_name
    return FileResponse(image_path)


@router.post("/upload-profile-image")
async def upload_profile_image(image: UploadFile = File(...), current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["id_utente"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    os.makedirs("uploads/profile", exist_ok=True)
    filename = f"profile_{user.id}.jpg"
    file_path = f"uploads/profile/{filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    user.image_profile = filename
    user.updated_user_datetime = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return {
        "message": "Immagine caricata",
        "image_profile": file_path,
        "updated_user_datetime": user.updated_user_datetime
    }


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if user:
        token = password_recovery_token(user.id)
        reset_link = f"pladdy://reset-password?token={token}"
        
        send_email(email= user.email, 
                  
                   obj = "Rigenera Password",
                   body= f"""
        <h2>Recupero password</h2>

        <p>Hai richiesto il reset della password.</p>

        <p>
            <a href="{reset_link}">
                Reimposta Password
            </a>
        </p>

        <p>Il link scadrà tra 1 ora.</p>""")
        
        # inviare push a tutti i dispositivi
        print(reset_link)
        return {
            "success": True,
            "token": token
        }
    return {"success": False}
  

@router.get("/reset-password")
def verify_reset_link(token: str):
    user_id = verify_reset_password(token)
    return {
        "valid": True,
        "user_id": user_id
    }


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
        user = User(nome_utente=user.nome_utente, email=user.email, password=hash_password_register(user.password), nickname=user.nickname)
        user.creation_user_datetime = datetime.now(timezone.utc)
        db.add(user)
        db.commit()
        db.refresh(user)
        return {
            "message": "Utente creato",
            "id": user.id
        }
    return {"message": "Utente già existent"}


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
            path = f"uploads/profile/{user.image_profile}"
            if os.path.exists(path):
                os.remove(path)
        
        db.query(Follow).filter((Follow.follower_id == user.id) | (Follow.followed_id == user.id)).delete(synchronize_session=False)
        db.query(TaskMentions).filter((TaskMentions.mentioned_user_id == user.id) | (TaskMentions.created_by_user_id == user.id)).delete(synchronize_session=False)
        db.query(Task).filter(Task.user_id == user.id).delete(synchronize_session=False)
        db.query(NotificationToken).filter(NotificationToken.id_user_ref == user.id).delete(synchronize_session=False)
        
        db.delete(user)
        db.commit()
        return {
            "success": True,
            "message": "Account eliminato"
        }
    except Exception:
        db.rollback()
        raise



'''
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy import or_ , and_
from firebase import invia_push, invia_push_silenziosa, invia_push_notifica, UnregisteredError
import re
from Auth.Auth import crea_token, crea_refresh_token, hash_password_register, hash_verify, get_current_user, verifica_refresh_token, password_recovery_token,verify_reset_password
from Models.models import (
    
    User,

    NotificationToken,

    Follow,

    TaskMentions,

    Task,

)
from Schemas.schemas import (
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
from fastapi import UploadFile,File
import shutil
import os
from pathlib import Path
from fastapi.responses import FileResponse
from mail.mail import send_reset_email

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



@router.get("/get-users")
def get_users(
    query: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    followed_users = (
    db.query(Follow.followed_id)
        .filter(
            Follow.follower_id == current_user["id_utente"]
        )
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




@router.get("/remove-friend")
def remove_friend(
    remove_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    follow = (

     db.query(Follow)

        .filter(
             Follow.request_accepted == True,
            or_(
                and_(
                    Follow.follower_id == current_user["id_utente"],
                    Follow.followed_id == remove_id,
                ),
                and_(
                    Follow.follower_id == remove_id,
                    Follow.followed_id == current_user["id_utente"],
                ),
            )
        )
        .first()
    )

    if not follow:
        raise HTTPException(
            status_code=404,
            detail="Amico non trovato"
        )

    db.delete(follow)
    db.commit()

    return {
        "success": True,
        "message": "Amico rimosso"
    }



@router.delete("/remove-mention")
def remove_mention(
    task_id: int,
    id_user_mentioned: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print("REMOVE MENTION CHIAMATO")

    # Recupero tutte le menzioni del task
    mentions = (
        db.query(TaskMentions)
        .filter(TaskMentions.task_id == task_id)
        .all()
    )

    if not mentions:
        raise HTTPException(status_code=404)

    
   
    # Verifico se l'utente corrente è il creatore del task
    is_creator = any(
        m.created_by_user_id == current_user["id_utente"]
        for m in mentions
    )
    
    print("CURRENT USER:", current_user["id_utente"])

    for m in mentions:

        print(

            f"mentioned={m.mentioned_user_id} "

            f"created_by={m.created_by_user_id}"

        )
        
        
    print("IS CREATOR:", is_creator)
    if is_creator:
        # Il creatore rimuove una qualsiasi menzione
        mention = (
            db.query(TaskMentions)
            .filter(
                TaskMentions.task_id == task_id,
                TaskMentions.mentioned_user_id == id_user_mentioned,
            )
            .first()
        )
    else:
        # Il menzionato può rimuovere solo se stesso
        mention = (
            db.query(TaskMentions)
            .filter(
                TaskMentions.task_id == task_id,
                TaskMentions.mentioned_user_id == current_user["id_utente"],
            )
            .first()
        )

    if not mention:
        raise HTTPException(status_code=404)

    task = (
        db.query(Task)
        .filter(Task.id_task == task_id)
        .first()
    )

    # Se il menzionato si rimuove da solo elimino anche @nickname dal titolo
    if task:

        user = (

            db.query(User)

            .filter(User.id == mention.mentioned_user_id)

            .first()

        )

        if user and user.nickname:

            task.titolo = (

                task.titolo

                .replace(f"@{user.nickname}", "")

                .replace("  ", " ")

                .strip()

            )
            task.titolo = re.sub(r"\s+", " ", task.titolo).strip()

    db.delete(mention)

    if task:
        task.datetime_task_last_update = datetime.now(timezone.utc)
        print("PRIMA COMMIT:", task.datetime_task_last_update)

    db.commit()

    if task:
        db.refresh(task)
        print("DOPO COMMIT:", task.datetime_task_last_update)

    # Push al proprietario del task (se non è chi ha eseguito la rimozione)
    print("TASK USER:", task.user_id)
    print("CURRENT USER:", current_user["id_utente"])

    if task and task.user_id != current_user["id_utente"]:
        print("ENTRO PUSH OWNER")

        tokens = (
            db.query(NotificationToken)
            .filter(NotificationToken.id_user_ref == task.user_id)
            .all()
        )

        print("TOKEN TROVATI:", len(tokens))

        for token in tokens:
            print("TOKEN:", token.fcm_token)
            print("CHIAMO INVIA_PUSH_SILENZIOSA")

            invia_push_silenziosa(
                token.fcm_token,
                "refresh",
            )

        print("FINE PUSH OWNER")
    else:
        print("NON ENTRO NEL BLOCCO OWNER")
    # Push a tutti gli utenti ancora menzionati
    remaining_mentions = (
        db.query(TaskMentions)
        .filter(TaskMentions.task_id == task_id)
        .all()
    )

    print("MENZIONI RIMASTE:", len(remaining_mentions))

    for m in remaining_mentions:

        if m.mentioned_user_id == current_user["id_utente"]:
            continue

        tokens = (
            db.query(NotificationToken)
            .filter(NotificationToken.id_user_ref == m.mentioned_user_id)
            .all()
        )

        print("PUSH MENTION:", m.mentioned_user_id)
        try:
            for token in tokens:
                invia_push_silenziosa(
                    token.fcm_token,
                    "refresh",
                )
                
        except UnregisteredError:

            db.query(NotificationToken).filter(

                NotificationToken.fcm_token == token.fcm_token

            ).delete()

            db.commit()

    return {
        "success": True
    }
# todo ritorna notifications-count ritorna count ,friend_request,, mentions

@router.get("/notifications-count")
def notifications_count(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    friend_requests = (
        db.query(Follow)
        .filter(
            Follow.followed_id == current_user["id_utente"],
            Follow.request_accepted == 0
        )
        .count()
    )

    mentions = (
        db.query(TaskMentions)
        .filter(
            TaskMentions.mentioned_user_id == current_user["id_utente"]
        )
        .count()
    )

    return {
        "count": friend_requests + mentions,
        "friend_requests": friend_requests,
        "mentions": mentions
    }


@router.get("/friend-requests-count")
def friend_requests_count(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    friend_requests = (
        db.query(Follow)
        .filter(
            Follow.followed_id == current_user["id_utente"],
            Follow.request_accepted == 0
        )
        .count()
    )
   
    return {
        "count": friend_requests ,       
    }


@router.get("/mentions-unread-count")
def mentions_unread_count(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    mentions = (
        db.query(TaskMentions)
        .filter(
            TaskMentions.mentioned_user_id == current_user["id_utente"],
            TaskMentions.notification_read == 0
        )
        .count()
    )

    return {
        "count": mentions ,
    }




@router.get("/get-mentions")
def get_mentions(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    
    mentions = (

    db.query(TaskMentions, User)
    .join(User, User.id == TaskMentions.mentioned_user_id)
    .filter(
        or_(
            TaskMentions.created_by_user_id == current_user["id_utente"],
            TaskMentions.mentioned_user_id == current_user["id_utente"]
        )
    )
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
        "is_shared_by_me":
            mention.created_by_user_id == current_user["id_utente"]
    }

        for mention, user in mentions

    ]



@router.get("/friend-requests")
def friend_requests(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    
    
    print("CURRENT USER", current_user["id_utente"])
    for f in db.query(Follow).all():
        print(
            f"id={f.id}, "
            f"follower={f.follower_id}, "
            f"followed={f.followed_id}, "
            f"accepted={f.request_accepted}"
        )
    users = (
        db.query(User, Follow.id)
        .join(
            Follow,
            User.id == Follow.follower_id
        )
        .filter(
            Follow.followed_id == current_user["id_utente"],
            Follow.request_accepted == False
        )
        .all()
    )
    
    for user, follow_id in users:

        print(f"user.id={user.id} follow_id={follow_id}")

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
def set_friend_request(
    data: FollowResponse,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    follow = (
        db.query(Follow)
        .filter(Follow.id == data.follow_id)
        .first()
    )

    if not follow:
        raise HTTPException(
            status_code=404,
            detail="Richiesta non trovata"
        )

    # Solo il destinatario può accettare/rifiutare

    if follow.followed_id != current_user["id_utente"]:
        raise HTTPException(
            status_code=403,
            detail="Operazione non consentita"
        )
        
    sender = (

        db.query(User)

        .filter(User.id == follow.follower_id)

        .first()

    )

    receiver = (

        db.query(User)

        .filter(User.id == follow.followed_id)

        .first()

    )
    
    
    if data.accepted:
        follow.request_accepted = True
        db.commit()
         # Token del destinatario
        tokens = (
            db.query(NotificationToken)
            .filter(NotificationToken.id_user_ref == sender.id)
            .all()
        )

        for token in tokens:
            try:
                invia_push_notifica(
                    token.fcm_token,
                    receiver.nickname,
                    receiver.id,
                    "Richiesta di amicizia",
                    f"{receiver.nickname} ha accettato la richiesta",
                    "friend_request"
                )
            except UnregisteredError:

                db.query(NotificationToken).filter(

                    NotificationToken.fcm_token == token.fcm_token

                ).delete()

                db.commit()



        return {

        "success": True

        }
    db.delete(follow)
    db.commit()
    return {
        "success": False
    }
    
    
    
@router.post("/add-friend")
def add_friend(
    data: AddFriendRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    receiver = (
        db.query(User)
        .filter(User.id == data.followed_id)
        .first()
    )

    if not receiver:
        raise HTTPException(
            status_code=404,
            detail="Utente non trovato"
        )

    if data.followed_id == current_user["id_utente"]:
        raise HTTPException(
            status_code=400,
            detail="Non puoi seguire te stesso"
        )

    existing = (
        db.query(Follow)
        .filter(
            or_(
                and_(
                    Follow.follower_id == current_user["id_utente"],
                    Follow.followed_id == data.followed_id,
                ),
                and_(
                    Follow.follower_id == data.followed_id,
                    Follow.followed_id == current_user["id_utente"],
                ),
            )
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Richiesta già esistente"
        )

    follow = Follow(
        follower_id=current_user["id_utente"],
        followed_id=data.followed_id,
        created_at=datetime.now(timezone.utc)
    )

    db.add(follow)
    db.commit()

    # Utente che ha inviato la richiesta
    sender = (
        db.query(User)
        .filter(User.id == current_user["id_utente"])
        .first()
    )

    # Token del destinatario
    tokens = (
        db.query(NotificationToken)
        .filter(NotificationToken.id_user_ref == receiver.id)
        .all()
    )

    for token in tokens:
        try:
            invia_push_notifica(
                token.fcm_token,
                sender.nickname,
                sender.id,
                "Nuova richiesta di amicizia",
                f"{sender.nickname} ti ha inviato una richiesta di amicizia",    
                "friend_request"
            )
        except UnregisteredError:

            db.query(NotificationToken).filter(

                NotificationToken.fcm_token == token.fcm_token

            ).delete()

            db.commit()


    return {
        "success": True,
        "nickname": receiver.nickname,
        "nome_utente": receiver.nome_utente,
        "image_profile": receiver.image_profile,
        "friend_id": receiver.id,
    }
    
    
    
    
@router.get("/get-friend")
def get_friend(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    users = (
    db.query(User)
    .join(
        Follow,
         or_(
              and_(
                  Follow.follower_id == current_user["id_utente"],
                  User.id == Follow.followed_id,
             ),
                and_(
                    Follow.followed_id == current_user["id_utente"],
                 User.id == Follow.follower_id,
              ),
          )
      )
        .filter(
            Follow.request_accepted == True
        )
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
async def register_token(
    request: TokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    token = (
        db.query(NotificationToken)
        .filter(NotificationToken.fcm_token == request.fcm_token)
        .first()
    )

    if token:
        token.id_user_ref = current_user["id_utente"]
    else:
        token = NotificationToken(
            fcm_token=request.fcm_token,
            id_user_ref=current_user["id_utente"]
        )
        db.add(token)

    db.commit()

    return {"message": "Token registrato"}
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
    user.updated_user_datetime = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return {
        "message": "Immagine caricata",
        "image_profile": file_path,
         "updated_user_datetime": user.updated_user_datetime

    }





@router.post("/forgot-password")

def forgot_password(data: ForgotPasswordRequest,db: Session = Depends(get_db)):

    user = db.query(User).filter(

        User.email == data.email

    ).first()

    if user:

        token = password_recovery_token(user.id)
        # genera token

        # salva token nel db
       
        
        reset_link = f"http://127.0.0.1:8000/user/reset-password?token={token}"

        # invia email
        #send_reset_email(user.email,reset_link)
        print(reset_link)

        return {

            "success": True,

            "token": token

        }
    return {"success": False}
  


@router.get("/reset-password")
def verify_reset_link(token: str):

    user_id = verify_reset_password(token)

    return {
        "valid": True,
        "user_id": user_id
    }

@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):

    user_id = verify_reset_password(data.token)

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Utente non trovato"
        )

    user.password = hash_password_register(
        data.new_password
    )

    db.commit()

    return {
        "message": "Password aggiornata"
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
        "image_profile": user.image_profile,
        "updated_user_datetime": user.updated_user_datetime
    }
    
@router.delete("/delete-profile")
def delete_profile(
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
        
    try:
        # Follow

        if user.image_profile:
            path = f"uploads/profile/{user.image_profile}"
            if os.path.exists(path):
                os.remove(path)
        
        db.query(Follow).filter(

            (Follow.follower_id == user.id) |

            (Follow.followed_id == user.id)

        ).delete(synchronize_session=False)

        # Menzioni

        db.query(TaskMentions).filter(

            (TaskMentions.mentioned_user_id == user.id) |

            (TaskMentions.created_by_user_id == user.id)

        ).delete(synchronize_session=False)

        # Task utente

        db.query(Task).filter(

            Task.user_id == user.id

        ).delete(synchronize_session=False)

        db.query(NotificationToken).filter(

            NotificationToken.id_user_ref == user.id

        ).delete(synchronize_session=False)
        
        db.delete(user)

        db.commit()

        return {

            "success": True,

            "message": "Account eliminato"

        }

    except Exception:

        db.rollback()

        raise
    
'''