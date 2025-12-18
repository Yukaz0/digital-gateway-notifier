# import logging
# import os
# import asyncio
# from telegram import Bot
# from telegram.constants import ParseMode
# from telegram.error import TelegramError


# class TelegramNotifier:
#     def __init__(self, loop: asyncio.AbstractEventLoop):
#         """
#         Inisialisasi Telegram Notifier menggunakan python-telegram-bot.
#         Membutuhkan asyncio event loop untuk berjalan secara thread-safe.
#         """
#         self.token = os.environ.get('TELEGRAM_BOT_TOKEN')
#         self.chat_id = os.environ.get('TELEGRAM_CHAT_ID')
#         self.loop = loop

#         if not self.token or not self.chat_id:
#             self.enabled = False
#             logging.warning("Konfigurasi Telegram (TOKEN/CHAT_ID) tidak ditemukan. Notifikasi Telegram dinonaktifkan.")
#         else:
#             self.enabled = True
#             # Buat instance Bot
#             self.bot = Bot(token=self.token)
#             logging.info("Telegram Notifier (python-telegram-bot) berhasil diinisialisasi.")

#     async def _async_send(self, message: str):
#         """
#         Coroutine asinkron yang sebenarnya bertugas mengirim pesan.
#         """
#         if not self.enabled:
#             return

#         try:
#             await self.bot.send_message(
#                 chat_id=self.chat_id,
#                 text=message,
#                 parse_mode=ParseMode.MARKDOWN_V2
#             )
#             logging.info(f"Pesan berhasil dikirim ke Telegram chat_id: {self.chat_id}")
#         except TelegramError as e:
#             # Tangani error spesifik dari Telegram API
#             logging.error(f"Gagal mengirim pesan ke Telegram: {e}")
#         except Exception as e:
#             logging.error(f"Terjadi error tak terduga saat mengirim pesan Telegram: {e}")

#     def send_message(self, message: str):
#         """
#         Method sinkron yang dipanggil dari thread lain (misal: Kafka consumer).
#         Tugasnya adalah menjadwalkan pengiriman pesan di event loop asyncio
#         secara aman (thread-safe).
#         """
#         if not self.enabled:
#             return

#         # Ganti karakter Markdown yang bisa menyebabkan error
#         safe_message = message.replace('.', '\\.').replace('-', '\\-').replace('!', '\\!').replace('(', '\\(').replace(
#             ')', '\\)')

#         # Menjadwalkan coroutine _async_send untuk dijalankan di loop
#         future = asyncio.run_coroutine_threadsafe(self._async_send(safe_message), self.loop)

#         try:
#             # (Opsional) Menunggu hasil selama 10 detik.
#             # Ini memastikan pesan setidaknya sudah coba dikirim sebelum lanjut.
#             future.result(timeout=10)
#         except Exception as e:
#             logging.error(f"Error saat menjadwalkan atau menunggu hasil pengiriman Telegram: {e}")