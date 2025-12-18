# bot/telegram_bot.py
import logging
import os
import asyncio
import re
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# Asumsi file-file ini ada dan berfungsi
from libs.database.db import DatabaseManager

# --- FUNGSI PEMBANTU BARU UNTUK KEAMANAN MARKDOWN ---
def escape_markdown_v2(text: str) -> str:
    """Mengamankan karakter spesial untuk mode parse MarkdownV2 Telegram."""
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


class TelegramBot:
    def __init__(self, token: str, loop: asyncio.AbstractEventLoop, db_manager: DatabaseManager, kafka_producer, whatsapp_notifier, kafka_consumer):
        """Menginisialisasi aplikasi bot lengkap dengan semua dependensi."""
        if not token:
            raise ValueError("Token Telegram harus disediakan.")
            
        self.loop = loop
        self.db_manager = db_manager
        self.kafka_producer = kafka_producer
        self.whatsapp_notifier = whatsapp_notifier
        self.kafka_consumer = kafka_consumer
        
        self.bot = Bot(token=token)
        self.application = Application.builder().token(token).build()

        # Daftarkan semua command handler
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("daftar", self.daftar))
        self.application.add_handler(CommandHandler("status", self.status_command))

        logging.info("Aplikasi Telegram Bot interaktif berhasil diinisialisasi.")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler untuk perintah /start."""
        chat_id = update.effective_chat.id
        try:
            pelanggan = self.db_manager.get_pelanggan_by_chat_id(str(chat_id))
            if pelanggan:
                safe_name = escape_markdown_v2(update.effective_user.first_name)
                safe_nomor_hp = escape_markdown_v2(pelanggan['nomor_hp'])
                message = (
                    f"👋 Halo {safe_name}\\!\n\n"
                    f"Akun Telegram Anda sudah terdaftar untuk nomor HP: *{safe_nomor_hp}*\\.\n\n"
                    "Anda akan menerima notifikasi alarm\\. Ketik /help untuk melihat panduan\\."
                )
            else:
                message = (
                    "👋 Selamat datang\\!\n\n"
                    "Akun Telegram Anda belum terdaftar\\. Gunakan perintah:\n\n"
                    "`/daftar <nomor_hp_terdaftar>`\n\n"
                    "Contoh: `/daftar +628123456789`"
                )
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            logging.error(f"Error di /start handler: {e}")
            await update.message.reply_text("Terjadi kesalahan saat memeriksa status registrasi.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler untuk perintah /help."""
        # --- PERBAIKAN UTAMA ADA DI SINI ---
        # Karakter < dan > sekarang di-escape dengan benar
        message = (
            "🤖 *Panduan Bot Notifikasi*\n\n"
            "*/start* \\- Cek status registrasi Anda\\.\n"
            "*/daftar \\<no\\_hp\\>* \\- Tautkan akun Telegram ke nomor HP\\.\n"
            "*/status* \\- Cek status kesehatan semua layanan\\.\n"
            "*/help* \\- Tampilkan pesan ini\\."
        )
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2)

    async def daftar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler untuk mendaftarkan chat_id ke nomor HP."""
        chat_id = str(update.effective_chat.id)
        try:
            nomor_hp = context.args[0]
        except IndexError:
            await update.message.reply_text("Format salah\\. Gunakan: `/daftar <nomor_hp>`", parse_mode=ParseMode.MARKDOWN_V2)
            return

        try:
            pelanggan = self.db_manager.get_pelanggan_by_nomor(nomor_hp=nomor_hp)
            if not pelanggan:
                await update.message.reply_text(f"Nomor HP {escape_markdown_v2(nomor_hp)} tidak ditemukan di sistem\\.", parse_mode=ParseMode.MARKDOWN_V2)
                return
            
            if pelanggan.get('telegram_chat_id') and pelanggan.get('telegram_chat_id') != chat_id:
                 await update.message.reply_text(f"Nomor HP {escape_markdown_v2(nomor_hp)} sudah ditautkan ke akun Telegram lain\\.", parse_mode=ParseMode.MARKDOWN_V2)
                 return

            if self.db_manager.register_telegram_user(nomor_hp=nomor_hp, chat_id=chat_id):
                await update.message.reply_text(f"✅ Berhasil\\! Akun Telegram Anda telah ditautkan ke nomor {escape_markdown_v2(nomor_hp)}\\.", parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await update.message.reply_text("Gagal memperbarui database\\.")
        except Exception as e:
            logging.error(f"Error saat proses daftar: {e}")
            await update.message.reply_text("Terjadi kesalahan internal saat mendaftar\\.")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler untuk perintah /status."""
        logging.info("Menerima permintaan /status...")
        status_lines = ["*📊 STATUS LAYANAN GATEWAY*"]
        
        try:
            db_status = "Terhubung" if self.db_manager.check_db_connection() else "❌ Gagal"
            status_lines.append(f"Database: {escape_markdown_v2(db_status)}")
        except Exception as e:
            status_lines.append(f"Database: ❌ Error \\- {escape_markdown_v2(str(e))}")
            
        try:
            producer_status = self.kafka_producer.check_status()
            status_lines.append(f"Kafka Producer: {escape_markdown_v2(producer_status)}")
        except Exception as e:
            status_lines.append(f"Kafka Producer: ❌ Error \\- {escape_markdown_v2(str(e))}")

        try:
            consumer_status = self.kafka_consumer.check_status()
            status_lines.append(f"Kafka Consumer: {escape_markdown_v2(consumer_status)}")
        except Exception as e:
            status_lines.append(f"Kafka Consumer: ❌ Error \\- {escape_markdown_v2(str(e))}")

        try:
            whatsapp_status = self.whatsapp_notifier.check_status()
            status_lines.append(f"WhatsApp \\(WAHA\\): {escape_markdown_v2(whatsapp_status)}")
        except Exception as e:
            status_lines.append(f"WhatsApp \\(WAHA\\): ❌ Error \\- {escape_markdown_v2(str(e))}")

        response_message = "\n".join(status_lines)
        await update.message.reply_text(response_message, parse_mode=ParseMode.MARKDOWN_V2)

    def run(self):
        """Menjalankan bot (polling) di thread saat ini."""
        logging.info("Memulai polling Telegram Bot...")
        self.application.run_polling()

    def send_notification(self, chat_id: str, message: str):
        """Menjadwalkan pengiriman pesan notifikasi di event loop bot."""
        if not self.loop.is_running():
            logging.warning("Event loop tidak berjalan, tidak bisa mengirim notifikasi Telegram.")
            return False
            
        safe_message = escape_markdown_v2(message)
        
        future = asyncio.run_coroutine_threadsafe(
            self.bot.send_message(chat_id=chat_id, text=safe_message, parse_mode=ParseMode.MARKDOWN_V2),
            self.loop
        )
        try:
            future.result(timeout=10)
            return True
        except Exception as e:
            logging.error(f"Error saat mengirim notifikasi Telegram ke {chat_id}: {e}")
            return False

    def set_kafka_consumer(self, consumer):
        """Memberi referensi ke Kafka consumer setelah dibuat."""
        self.kafka_consumer = consumer

