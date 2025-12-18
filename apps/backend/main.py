import asyncio
import logging
import os
from threading import Thread
from typing import List

from confluent_kafka import Consumer
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from psycopg2.extras import RealDictCursor

from . import crud
from . import schemas
from . import auth
from libs.database.db import get_db_connection, get_db


# --- Manajer Koneksi WebSocket ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()

# --- Aplikasi FastAPI ---
app = FastAPI(
    title="Gateway Admin API",
    description="API untuk mengelola pelanggan dan memonitor gateway notifikasi.",
    version="1.0.0"
)

# Konfigurasi CORS
origins = ["http://localhost", "http://localhost:3000", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Kafka Consumer untuk Backend API (Log Notifikasi) ---
def start_api_kafka_consumer(loop: asyncio.AbstractEventLoop):
    """Tugas ini berjalan di thread background, mendengarkan log notifikasi."""
    conf = {
        'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS'),
        'group.id': 'api_log_consumer_group',
        'auto.offset.reset': 'latest'
    }
    # Pastikan env var untuk topic log ada
    log_topic = os.environ.get('NOTIFICATION_LOGS_TOPIC')
    if not log_topic:
        logging.error("Environment variable NOTIFICATION_LOGS_TOPIC tidak diatur. Consumer log tidak akan berjalan.")
        return

    consumer = Consumer(conf)
    consumer.subscribe([log_topic])
    logging.info(f"API Kafka Consumer terhubung dan mendengarkan topic: {log_topic}")

    while True:
        msg = consumer.poll(1.0)
        if msg is None: continue
        if msg.error():
            logging.error(f"API Kafka Consumer Error: {msg.error()}")
            continue

        log_message = msg.value().decode('utf-8')
        logging.info(f"API Menerima log notifikasi: {log_message}")

        # Menyiarkan pesan ke semua klien WebSocket dengan aman dari thread ini
        asyncio.run_coroutine_threadsafe(manager.broadcast(log_message), loop)


@app.on_event("startup")
async def startup_event():
    """Jalankan Kafka consumer di thread terpisah saat aplikasi dimulai."""
    loop = asyncio.get_running_loop()

    consumer_thread = Thread(target=start_api_kafka_consumer, args=(loop,), daemon=True)
    consumer_thread.start()


# --- Endpoint WebSocket ---
@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Biarkan koneksi terbuka untuk menjaga koneksi tetap hidup
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def get_db():
    conn = get_db_connection()
    try:
        yield conn.cursor()
    finally:
        conn.close()


@app.get("/", tags=["Status"])
def read_root():
    return {"status": "API is running"}


# --- Endpoint untuk Pelanggan ---

@app.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED, tags=["Autentikasi"])
def register_user(user: schemas.UserCreate, db: RealDictCursor = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar.")
    new_user = crud.create_user(db, user)
    db.connection.commit()
    return new_user


@app.post("/token", response_model=schemas.Token, tags=["Autentikasi"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(),
                                 db: RealDictCursor = Depends(get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth.verify_password(form_data.password, user['hashed_password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Buat token baru
    access_token = auth.create_access_token(data={"sub": user['username']})

    # Simpan token baru ini sebagai token aktif di database
    crud.update_active_token(db, username=user['username'], token=access_token)
    db.connection.commit()

    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/logout", status_code=status.HTTP_200_OK, tags=["Autentikasi"])
async def logout_user(current_user: dict = Depends(auth.get_current_user), db: RealDictCursor = Depends(get_db)):
    """
    Logout user dengan menghapus token aktif mereka dari database.
    """
    # Hapus token aktif dari DB (set menjadi NULL)
    crud.update_active_token(db, username=current_user['username'], token=None)
    db.connection.commit()
    return {"message": "Successfully logged out"}

@app.post("/pelanggan", response_model=schemas.Pelanggan, status_code=status.HTTP_201_CREATED, tags=["Pelanggan"])
def create_new_pelanggan(pelanggan: schemas.PelangganCreate, db: RealDictCursor = Depends(get_db)):
    db_pelanggan = crud.get_pelanggan_by_nomor(db, nomor_hp=pelanggan.nomor_hp)
    if db_pelanggan:
        raise HTTPException(status_code=400, detail="Nomor HP sudah terdaftar.")

    new_pelanggan = crud.create_pelanggan(db, pelanggan.dict())
    db.connection.commit()
    return new_pelanggan


@app.get("/pelanggan", response_model=List[schemas.Pelanggan], tags=["Pelanggan"])
def read_all_pelanggan(skip: int = 0, limit: int = 100, db: RealDictCursor = Depends(get_db)):
    pelanggan_list = crud.get_all_pelanggan(db, skip=skip, limit=limit)
    return pelanggan_list


@app.get("/pelanggan/{nomor_hp}", response_model=schemas.Pelanggan, tags=["Pelanggan"])
def read_pelanggan(nomor_hp: str, db: RealDictCursor = Depends(get_db)):
    db_pelanggan = crud.get_pelanggan_by_nomor(db, nomor_hp=nomor_hp)
    if db_pelanggan is None:
        raise HTTPException(status_code=404, detail="Pelanggan tidak ditemukan.")
    return db_pelanggan


@app.put("/pelanggan/{nomor_hp}", response_model=schemas.Pelanggan, tags=["Pelanggan"])
def update_existing_pelanggan(nomor_hp: str, pelanggan_update: schemas.PelangganUpdate,
                              db: RealDictCursor = Depends(get_db)):
    db_pelanggan = crud.get_pelanggan_by_nomor(db, nomor_hp=nomor_hp)
    if db_pelanggan is None:
        raise HTTPException(status_code=404, detail="Pelanggan tidak ditemukan.")

    update_data = pelanggan_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Tidak ada data untuk diupdate.")

    updated_pelanggan = crud.update_pelanggan(db, nomor_hp=nomor_hp, update_data=update_data)
    db.connection.commit()
    return updated_pelanggan


@app.delete("/pelanggan/{nomor_hp}", response_model=schemas.Pelanggan, tags=["Pelanggan"])
def delete_existing_pelanggan(nomor_hp: str, db: RealDictCursor = Depends(get_db)):
    deleted_pelanggan = crud.delete_pelanggan(db, nomor_hp=nomor_hp)
    if deleted_pelanggan is None:
        raise HTTPException(status_code=404, detail="Pelanggan tidak ditemukan.")
    db.connection.commit()
    return deleted_pelanggan
