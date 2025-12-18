import os

from psycopg2.extras import RealDictCursor

from . import crud
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from libs.database.db import get_db

load_dotenv()

# --- Konfigurasi Keamanan ---
SECRET_KEY = os.environ.get("SECRET_KEY", "kunci_rahasia_default_yang_harus_diganti")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Fungsi-fungsi Keamanan ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Memverifikasi password polos dengan password yang sudah di-hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Membuat hash dari password polos."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Membuat JSON Web Token (JWT) baru.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: RealDictCursor = Depends(get_db)):
    """
    Dependency FastAPI untuk memverifikasi token dan mendapatkan data pengguna.
    Sekarang juga memeriksa apakah token adalah sesi yang aktif di database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        # --- VALIDASI BARU ---
        # 1. Ambil data user beserta token aktif dari database
        user = crud.get_user_with_token(db, username=username)
        if user is None:
            raise credentials_exception

        # 2. Bandingkan token dari klien dengan token di database
        if not user['active_jwt'] or user['active_jwt'] != token:
            # Jika token di DB kosong atau tidak sama, berarti sesi ini tidak valid
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is no longer valid. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user
    except JWTError:
        raise credentials_exception