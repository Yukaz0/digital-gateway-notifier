from typing import Optional

from psycopg2.extras import RealDictCursor
from . import auth
from . import schemas


def get_pelanggan_by_nomor(db: RealDictCursor, nomor_hp: str):
    """Mencari satu pelanggan berdasarkan nomor HP."""
    db.execute("SELECT * FROM pelanggan WHERE nomor_hp = %s", (nomor_hp,))
    return db.fetchone()

def get_all_pelanggan(db: RealDictCursor, skip: int = 0, limit: int = 100):
    """Mengambil semua data pelanggan dengan limitasi dan offset."""
    db.execute("SELECT * FROM pelanggan ORDER BY nama OFFSET %s LIMIT %s", (skip, limit))
    return db.fetchall()

def get_pelanggan_by_chat_id(db: RealDictCursor, chat_id: str):
    """Mencari satu pelanggan berdasarkan telegram_chat_id."""
    db.execute("SELECT * FROM pelanggan WHERE telegram_chat_id = %s", (chat_id,))
    return db.fetchone()

# --- Fungsi untuk menulis/mengubah data ---

def create_pelanggan(db: RealDictCursor, pelanggan: dict):
    """Membuat pelanggan baru di database."""
    columns = pelanggan.keys()
    values = [pelanggan[column] for column in columns]
    insert_query = f"""
        INSERT INTO pelanggan ({', '.join(columns)}) 
        VALUES ({', '.join(['%s'] * len(values))}) 
        RETURNING *;
    """
    db.execute(insert_query, tuple(values))
    return db.fetchone()

def update_pelanggan(db: RealDictCursor, nomor_hp: str, update_data: dict):
    """Memperbarui data pelanggan yang sudah ada."""
    set_query_parts = [f"{key} = %s" for key in update_data.keys()]
    set_query = ", ".join(set_query_parts)
    values = list(update_data.values())
    values.append(nomor_hp)
    update_query = f"UPDATE pelanggan SET {set_query} WHERE nomor_hp = %s RETURNING *;"
    db.execute(update_query, tuple(values))
    return db.fetchone()

def delete_pelanggan(db: RealDictCursor, nomor_hp: str):
    """Menghapus pelanggan dari database."""
    db.execute("DELETE FROM pelanggan WHERE nomor_hp = %s RETURNING *;", (nomor_hp,))
    return db.fetchone()

def register_telegram_user(db: RealDictCursor, nomor_hp: str, chat_id: str):
    """Mengupdate telegram_chat_id untuk pelanggan."""
    db.execute(
        'UPDATE pelanggan SET telegram_chat_id = %s, telegram = TRUE WHERE nomor_hp = %s',
        (chat_id, nomor_hp)
    )
    return True

def check_db_connection(db: RealDictCursor):
    """Mengecek koneksi database dengan menjalankan query sederhana."""
    try:
        db.execute('SELECT 1')
        return True
    except Exception:
        return False

def get_user_by_username(db: RealDictCursor, username: str):
    """Mencari satu user berdasarkan username untuk verifikasi login."""
    db.execute("SELECT * FROM users_smsgateway WHERE username = %s", (username,))
    return db.fetchone()

def get_user_with_token(db: RealDictCursor, username: str):
    """Mencari satu user berdasarkan username dan mengambil token aktifnya."""
    db.execute("SELECT id, username, active_jwt FROM users_smsgateway WHERE username = %s", (username,))
    return db.fetchone()

def update_active_token(db: RealDictCursor, username: str, token: Optional[str]):
    """Menyimpan atau menghapus token JWT aktif untuk seorang user."""
    db.execute(
        "UPDATE users_smsgateway SET active_jwt = %s WHERE username = %s",
        (token, username)
    )
    return True

def create_user(db: RealDictCursor, user: schemas.UserCreate):
    """Membuat user baru dengan password yang sudah di-hash."""
    hashed_password = auth.get_password_hash(user.password)
    insert_query = """
        INSERT INTO users_smsgateway (username, hashed_password) 
        VALUES (%s, %s) 
        RETURNING id, username;
    """
    db.execute(insert_query, (user.username, hashed_password))
    return db.fetchone()


# --- Fungsi CRUD untuk Name Station Gateway ---

def get_all_name_stations(db: RealDictCursor, skip: int = 0, limit: int = 100):
    """Mengambil semua data name station gateway dengan paginasi."""
    db.execute(
        "SELECT * FROM name_station_gateway ORDER BY name_station OFFSET %s LIMIT %s",
        (skip, limit)
    )
    return db.fetchall()

def get_name_station_by_id(db: RealDictCursor, station_id: int):
    """Mencari satu name station berdasarkan ID."""
    db.execute("SELECT * FROM name_station_gateway WHERE id = %s", (station_id,))
    return db.fetchone()

def create_name_station(db: RealDictCursor, data: dict):
    """Membuat name station baru di database."""
    insert_query = """
        INSERT INTO name_station_gateway (name_station, singkatan_name_station, code_station, keterangan)
        VALUES (%s, %s, %s, %s)
        RETURNING *;
    """
    db.execute(insert_query, (
        data['name_station'],
        data.get('singkatan_name_station'),
        data['code_station'],
        data.get('keterangan')
    ))
    return db.fetchone()

def update_name_station(db: RealDictCursor, station_id: int, update_data: dict):
    """Memperbarui data name station yang sudah ada."""
    set_query_parts = [f"{key} = %s" for key in update_data.keys()]
    set_query_parts.append("update_date = CURRENT_TIMESTAMP")
    set_query = ", ".join(set_query_parts)
    values = list(update_data.values())
    values.append(station_id)
    update_query = f"UPDATE name_station_gateway SET {set_query} WHERE id = %s RETURNING *;"
    db.execute(update_query, tuple(values))
    return db.fetchone()

def delete_name_station(db: RealDictCursor, station_id: int):
    """Menghapus name station dari database."""
    db.execute("DELETE FROM name_station_gateway WHERE id = %s RETURNING *;", (station_id,))
    return db.fetchone()


def bulk_create_name_stations(db: RealDictCursor, rows: list):
    """Bulk insert name stations. Returns dict with 'success_count' and 'errors' list."""
    success_count = 0
    errors = []

    for i, row in enumerate(rows):
        try:
            insert_query = """
                INSERT INTO name_station_gateway (name_station, singkatan_name_station, code_station, keterangan)
                VALUES (%s, %s, %s, %s);
            """
            db.execute(insert_query, (
                row.get('name_station', '').strip(),
                row.get('singkatan_name_station', '').strip() or None,
                row.get('code_station', '').strip(),
                row.get('keterangan', '').strip() or None,
            ))
            success_count += 1
        except Exception as e:
            # Rollback the failed statement but continue with next rows
            db.connection.rollback()
            error_msg = str(e).split('\n')[0]
            errors.append({"row": i + 1, "code_station": row.get('code_station', ''), "error": error_msg})

    return {"success_count": success_count, "errors": errors}