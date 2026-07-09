from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Depends
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from jose import JWTError, ExpiredSignatureError

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Depends
from jose import jwt, JWTError, ExpiredSignatureError
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

SECRET_KEY = "chiavesegreta"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
ACCESS_REFRESH_TOKEN_EXPIRE_DAYS = 30

DEBUG_ACCESS_TOKEN_EXPIRE_MINUTES = 30
DEBUG_ACCESS_REFRESH_TOKEN_EXPIRE_DAYS = 5

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login")

def get_current_user_web_socket(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        id_utente = payload.get("id")

        if email is None:
            raise HTTPException(status_code=401, detail="Token non valido")

        return {"email": email, "id_utente": id_utente}
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token non valido",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_reset_password(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "password_reset":
            raise HTTPException(status_code=400, detail="Token non valido")

        return int(payload["sub"])
    except ExpiredSignatureError:
        # 🟢 Intercettato correttamente: il client riceverà un 400 con "Token scaduto"
        raise HTTPException(status_code=400, detail="Token scaduto")
    except JWTError:
        raise HTTPException(status_code=400, detail="Token non valido")

def password_recovery_token(userid: int):
    token = jwt.encode(
        {
            "sub": str(userid),
            "type": "password_reset",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1) # 🟢 Scadenza reale a 1 ora
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return token

def crea_token(data: dict):
    to_encode = data.copy()
    # 🟢 Uniformato a datetime.now(timezone.utc)
    expire = datetime.now(timezone.utc) + timedelta(minutes=DEBUG_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access_token"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def crea_refresh_token(data: dict):
    to_encode = data.copy()
    # 🟢 Uniformato a datetime.now(timezone.utc)
    expire = datetime.now(timezone.utc) + timedelta(days=DEBUG_ACCESS_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh_token"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verifica_refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "refresh_token":
            raise HTTPException(status_code=401, detail="Token non valido")

        user_id = payload.get("id")
        email = payload.get("sub")

        new_access = crea_token({"sub": email, "id": user_id})
        return {"access_token": new_access}
    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh token scaduto")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        id_utente = payload.get("id")

        if email is None:
            raise HTTPException(status_code=401, detail="Token non valido")

        return {"email": email, "id_utente": id_utente}
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token non valido",
            headers={"WWW-Authenticate": "Bearer"},
        )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password_register(password: str):
    return pwd_context.hash(password)

def hash_verify(password_plain: str, hashed_password: str):
    return pwd_context.verify(password_plain, hashed_password)

'''
SECRET_KEY = "chiavesegreta"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
ACCESS_REFRESH_TOKEN_EXPIRE_DAYS =30

DEBUG_ACCESS_TOKEN_EXPIRE_MINUTES =  30
DEBUG_ACCESS_REFRESH_TOKEN_EXPIRE_DAYS = 5

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login")

def get_current_user_web_socket(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        email = payload.get("sub")
        id_utente = payload.get("id")

        if email is None:
            raise HTTPException(status_code=401, detail="Token non valido")

        return {"email": email, "id_utente": id_utente}

    except JWTError:
        raise HTTPException(
            status_code = 401,
            detail="Token non valido",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_reset_password(token: str) -> int:

    try:

        payload = jwt.decode(

            token,

            SECRET_KEY,

            algorithms=[ALGORITHM]

        )

        if payload.get("type") != "password_reset":

            raise HTTPException(

                status_code=400,

                detail="Token non valido"

            )

        return int(payload["sub"])

    except ExpiredSignatureError:

        raise HTTPException(

            status_code=400,

            detail="Token scaduto"

        )

    except JWTError:

        raise HTTPException(

            status_code=400,

            detail="Token non valido"

        )

def password_recovery_token(userid: int):
    token = jwt.encode(
        {
            "sub": str(userid),

            "type": "password_reset",

            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        },
        SECRET_KEY,
        algorithm="HS256"
    )
    return token

def crea_token(data: dict):
    to_encode = data.copy()
    # delta era minutes ma per test lo metto a secondi
    expire = datetime.utcnow() + timedelta(minutes=DEBUG_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire,"type":"access_token"})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def crea_refresh_token(data: dict):
    to_encode = data.copy()
    # delta era days ma per test lo metto a minuti
    expire = datetime.utcnow() + timedelta(days=DEBUG_ACCESS_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire,"type":"refresh_token"})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verifica_refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(
            refresh_token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        # controlla che sia refresh token
        if payload.get("type") != "refresh_token":
            raise HTTPException(status_code=401, detail="Token non valido")

        user_id = payload.get("id")
        email = payload.get("sub")

        # crea nuovo access token
        new_access = crea_token({
            "sub": email,
            "id": user_id
        })

        return {
            "access_token": new_access
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh token scaduto")

def get_current_user(token: str = Depends(oauth2_scheme)):

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        email = payload.get("sub")
        id_utente = payload.get("id")

        if email is None:
            raise HTTPException(status_code=401, detail="Token non valido")

        return {"email": email, "id_utente": id_utente}

    except JWTError:
        raise HTTPException(
            status_code = 401,
            detail="Token non valido",
            headers={"WWW-Authenticate": "Bearer"},
        )

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def hash_password_register(password: str):
    return pwd_context.hash(password)

def hash_verify(password_plain:str, hashed_password:str):
    return pwd_context.verify(password_plain, hashed_password)

'''
