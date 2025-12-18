import psycopg2
import logging
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Construct DATABASE_URL for use by get_db_connection
DATABASE_URL = (
    f"postgresql://{os.environ.get('POSTGRES_USER')}"
    f":{os.environ.get('POSTGRES_PASSWORD')}"
    f"@{os.environ.get('POSTGRES_HOST')}"
    f":{os.environ.get('POSTGRES_PORT')}"
    f"/{os.environ.get('POSTGRES_DBNAME')}"
)

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Gagal terhubung ke database: {e}")
        raise

def get_db():
    conn = get_db_connection()
    try:
        yield conn.cursor()
    finally:
        conn.commit()
        conn.close()

class DatabaseManager:
    def __init__(self):
        """
        Inisialisasi DatabaseManager dengan memuat konfigurasi
        langsung dari environment variables.
        """
        self.conn = None
        db_name = os.environ.get('POSTGRES_DBNAME')
        db_user = os.environ.get('POSTGRES_USER')
        db_password = os.environ.get('POSTGRES_PASSWORD')
        db_host = os.environ.get('POSTGRES_HOST')
        db_port = os.environ.get('POSTGRES_PORT')

        required_vars = {
            'POSTGRES_DBNAME': db_name, 'POSTGRES_USER': db_user, 
            'POSTGRES_PASSWORD': db_password, 'POSTGRES_HOST': db_host, 
            'POSTGRES_PORT': db_port
        }
        missing_vars = [key for key, value in required_vars.items() if value is None]
        if missing_vars:
            error_msg = f"Environment variable berikut tidak ditemukan: {', '.join(missing_vars)}"
            logging.critical(error_msg)
            raise ValueError(error_msg)

        try:
            self.conn = psycopg2.connect(
                dbname=db_name, user=db_user, password=db_password, 
                host=db_host, port=db_port
            )
            logging.info(f"Berhasil terhubung ke database PostgreSQL di host {db_host}")
        except psycopg2.OperationalError as e:
            logging.error(f"Gagal terhubung ke PostgreSQL: {e}")
            raise

    def get_cursor(self):
        """Mendapatkan cursor dictionary untuk query."""
        return self.conn.cursor(cursor_factory=RealDictCursor)

    def setup_tables(self):
        """Membuat tabel jika belum ada, dengan semua kolom yang diperlukan."""
        if not self.conn:
            logging.error("Koneksi database tidak tersedia, tidak dapat setup tabel.")
            return
        
        try:
            with self.conn.cursor() as cursor:
                # Membuat tabel pelanggan dengan struktur lengkap
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pelanggan (
                        id SERIAL PRIMARY KEY,
                        nama TEXT,
                        nomor_hp TEXT UNIQUE NOT NULL,
                        idpel TEXT,
                        kelas_notifikasi INTEGER[] DEFAULT ARRAY[4]::INTEGER[],
                        telegram BOOLEAN DEFAULT FALSE,
                        whatsapp BOOLEAN DEFAULT FALSE,
                        telegram_chat_id VARCHAR(20) UNIQUE NULL,
                        jabatan VARCHAR(50)
                    );
                ''')
                cursor.execute('''
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'pelanggan'
                            AND column_name = 'kelas_notifikasi'
                            AND udt_name <> '_int4'
                        ) THEN
                            ALTER TABLE pelanggan
                                ALTER COLUMN kelas_notifikasi DROP DEFAULT;

                            ALTER TABLE pelanggan
                                ALTER COLUMN kelas_notifikasi TYPE INTEGER[]
                                USING CASE
                                    WHEN kelas_notifikasi IS NULL THEN ARRAY[4]::INTEGER[]
                                    ELSE ARRAY[kelas_notifikasi]::INTEGER[]
                                END;

                            ALTER TABLE pelanggan
                                ALTER COLUMN kelas_notifikasi SET DEFAULT ARRAY[4]::INTEGER[];
                        END IF;
                    END $$;
                ''')
                
                # Tabel User
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users_smsgateway (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        hashed_password TEXT NOT NULL,
                        active_jwt TEXT NULL
                    );
                ''')
                cursor.execute('''
                    DO $$
                    BEGIN
                        IF NOT EXISTS(SELECT * FROM information_schema.columns 
                            WHERE table_name='users_smsgateway' AND column_name='active_jwt')
                        THEN
                            ALTER TABLE users_smsgateway ADD COLUMN active_jwt TEXT NULL;
                        END IF;
                    END $$;
                ''')
            self.conn.commit()
            logging.info("Tabel 'pelanggan' dan 'users_smsgateway' siap digunakan.")
        except Exception as e:
            logging.error(f"Gagal melakukan setup tabel: {e}")
            self.conn.rollback()

    def get_pelanggan_by_nomor(self, nomor_hp: str):
        """Mencari pelanggan berdasarkan nomor HP."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute('SELECT * FROM pelanggan WHERE nomor_hp = %s', (nomor_hp,))
                return cursor.fetchone()
        except psycopg2.Error as e:
            logging.error(f"Gagal mengambil pelanggan dari DB: {e}")
            self.conn.rollback()
            return None
            
    def get_pelanggan_by_chat_id(self, chat_id: str):
        """Mencari pelanggan berdasarkan telegram_chat_id."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute('SELECT * FROM pelanggan WHERE telegram_chat_id = %s', (chat_id,))
                return cursor.fetchone()
        except psycopg2.Error as e:
            logging.error(f"Gagal mengambil pelanggan dari DB via chat_id: {e}")
            self.conn.rollback()
            return None

    def register_telegram_user(self, nomor_hp: str, chat_id: str):
        """Mengupdate telegram_chat_id dan mengaktifkan notifikasi telegram."""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    'UPDATE pelanggan SET telegram_chat_id = %s, telegram = TRUE WHERE nomor_hp = %s',
                    (chat_id, nomor_hp)
                )
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            logging.error(f"Gagal mendaftarkan user telegram: {e}")
            self.conn.rollback()
            return False

    def get_recipients_by_priority(self, priority_level: int):
        """
        Mengambil daftar penerima yang memenuhi syarat berdasarkan prioritas.
        """
        if not self.conn:
            logging.error("Koneksi database tidak tersedia.")
            return []

        recipients = []
        try:
            # Menggunakan RealDictCursor agar hasilnya sudah dalam bentuk dictionary
            with self.get_cursor() as cursor:
                sql = """
                    SELECT nomor_hp, telegram, whatsapp, telegram_chat_id
                    FROM pelanggan
                    WHERE %s = ANY(kelas_notifikasi)
                """
                cursor.execute(sql, (priority_level,))
                recipients = cursor.fetchall()
        except psycopg2.Error as e:
            logging.error(f"Gagal mengambil penerima berdasarkan prioritas {priority_level}: {e}")
            self.conn.rollback()
            
        return recipients

    def check_db_connection(self):
        """Mengecek koneksi database dengan menjalankan query sederhana."""
        if not self.conn:
            return False
        try:
            with self.conn.cursor() as cursor:
                cursor.execute('SELECT 1')
            return True
        except psycopg2.Error:
            return False

    def close(self):
        if self.conn:
            self.conn.close()
            logging.info("Koneksi database ditutup.")