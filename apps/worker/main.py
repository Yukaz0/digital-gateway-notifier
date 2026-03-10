import logging
import os
import sys
import asyncio
import time
from threading import Thread
from dotenv import load_dotenv
from libs.utils.logging_config import setup_logging

# Impor dari semua komponen kita
from libs.database.db import DatabaseManager
from libs.kafka_client.kafka_manager import KafkaProducer, KafkaAlarmConsumer
from libs.bot.telegram_bot import TelegramBot
from libs.notifiers.whatsapp import WhatsappNotifier

load_dotenv()
setup_logging(level=os.environ.get('LOG_LEVEL', 'INFO'), service_name='NOTIFICATION CONSUMER')

HEALTH_CHECK_INTERVAL = 30  # detik


def start_asyncio_loop(loop: asyncio.AbstractEventLoop):
    """Fungsi target untuk thread yang akan menjalankan event loop asyncio."""
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    finally:
        tasks = asyncio.all_tasks(loop=loop)
        for task in tasks:
            task.cancel()
        group = asyncio.gather(*tasks, return_exceptions=True)
        loop.run_until_complete(group)
        loop.close()


def watchdog(consumer_thread: Thread, kafka_consumer):
    """
    Watchdog daemon: monitor kesehatan consumer thread.
    Jika thread mati, paksa exit agar Docker restart container.
    """
    while True:
        time.sleep(HEALTH_CHECK_INTERVAL)

        if not consumer_thread.is_alive():
            logging.critical("❌ Kafka Consumer thread MATI! Trigger full restart...")
            os._exit(1)

        if not kafka_consumer.is_healthy:
            logging.warning("⚠️ Kafka Consumer unhealthy, tapi thread masih hidup. Menunggu reconnect...")


def main():
    """
    Fungsi utama untuk menginisialisasi dan menjalankan semua service gateway.
    Telegram bot jalan di main thread (required untuk signal handlers).
    Watchdog jalan di background daemon thread.
    """
    logging.info("Memuat konfigurasi dari environment variables...")

    asyncio_loop = asyncio.new_event_loop()
    loop_thread = Thread(target=start_asyncio_loop, args=(asyncio_loop,), daemon=True)
    loop_thread.start()
    logging.info("Asyncio event loop untuk notifikasi telah dimulai di background.")

    db, kafka_producer, kafka_consumer, telegram_bot, whatsapp_notifier = None, None, None, None, None

    try:
        # 1. Inisialisasi komponen dasar
        db = DatabaseManager()
        db.setup_tables()
        kafka_producer = KafkaProducer()
        whatsapp_notifier = WhatsappNotifier()

        # 2. Inisialisasi Kafka Consumer
        kafka_consumer = KafkaAlarmConsumer(
            db_manager=db,
            whatsapp_notifier=whatsapp_notifier,
            kafka_manager=kafka_producer
        )

        # 3. Inisialisasi Bot Telegram
        telegram_bot = TelegramBot(
            token=os.environ.get('TELEGRAM_BOT_TOKEN'),
            loop=asyncio_loop,
            kafka_producer=kafka_producer,
            whatsapp_notifier=whatsapp_notifier,
            kafka_consumer=kafka_consumer,
            db_manager=db
        )

        # 4. Tautkan bot ke consumer
        kafka_consumer.set_telegram_bot(telegram_bot)

        # --- Jalankan Consumer di background ---
        consumer_thread = Thread(target=kafka_consumer.start_consuming, daemon=True)
        consumer_thread.start()

        # --- Jalankan Watchdog di background ---
        watchdog_thread = Thread(target=watchdog, args=(consumer_thread, kafka_consumer), daemon=True)
        watchdog_thread.start()
        logging.info("Semua service telah dimulai. Watchdog aktif.")

        # --- Telegram bot di main thread (required untuk signal handlers) ---
        logging.info("Memulai Telegram bot di main thread...")
        telegram_bot.run()

    except ValueError as e:
        logging.critical(f"Error Konfigurasi: {e}. Aplikasi berhenti.")
    except KeyboardInterrupt:
        logging.info("Aplikasi dihentikan oleh pengguna (Ctrl+C).")
    except Exception as e:
        logging.critical(f"Terjadi error fatal: {e}", exc_info=True)
    finally:
        logging.info("Memulai proses shutdown aplikasi...")
        if asyncio_loop.is_running():
            logging.info("Menghentikan asyncio event loop...")
            asyncio_loop.call_soon_threadsafe(asyncio_loop.stop)
        if db:
            db.close()
        if kafka_producer:
            kafka_producer.close()
        if kafka_consumer:
            kafka_consumer.close()
        logging.info("Aplikasi dihentikan. (Docker akan auto-restart jika configured)")
        sys.exit(1)

if __name__ == "__main__":
    main()