import logging
import os
import requests


class WhatsappNotifier:
    def __init__(self):
        """
        Inisialisasi WhatsApp Notifier yang terhubung ke WAHA (WhatsApp HTTP API).
        """
        # Ambil konfigurasi dari .env
        self.api_url = os.environ.get('WAHA_API_URL', 'http://localhost:3000')
        self.session_name = os.environ.get('WAHA_SESSION_NAME', 'default')
        self.api_key = os.environ.get('WAHA_API_KEY')

        # Nonaktifkan jika API Key tidak ada
        if not self.api_key:
            self.enabled = False
            logging.warning("Konfigurasi WAHA_API_KEY tidak ditemukan. Notifikasi WhatsApp dinonaktifkan.")
        else:
            self.enabled = True
            logging.info(
                f"WhatsApp Notifier (WAHA) diinisialisasi. Endpoint: {self.api_url}, Session: {self.session_name}")

    def check_status(self):
        """Mengecek status koneksi ke server WAHA."""
        if not self.enabled:
            return "Dinonaktifkan"
        try:
            response = requests.get(f"{self.api_url}/ping", timeout=5)
            if response.status_code == 200 and "pong" in response.text:
                return "Terhubung"
            else:
                return f"Error (Status: {response.status_code})"
        except requests.RequestException:
            return "Gagal Terhubung"

    def send_message(self, to_number: str, message: str):
        """
        Mengirim pesan WhatsApp dengan memanggil endpoint yang benar dari WAHA,
        menyertakan nama sesi di payload dan API Key di header.
        """
        if not self.enabled:
            return False

        # WAHA memerlukan nomor dalam format <nomor>@c.us
        if to_number.startswith('+'):
            to_number = to_number[1:]

        chat_id = f"{to_number}@c.us"

        send_text_url = f"{self.api_url}/api/sendText"

        payload = {
            'chatId': chat_id,
            'text': message,
            'session': self.session_name
        }

        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': self.api_key
        }

        try:
            response = requests.post(send_text_url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            logging.info(f"Pesan WhatsApp berhasil dikirim ke {to_number} via WAHA.")
            return True
        except requests.RequestException as e:
            logging.error(f"Gagal menghubungi WAHA API: {e}")
            if e.response is not None:
                logging.error(f"Respons dari server WAHA: {e.response.text}")
            return False