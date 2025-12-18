import serial
import time
import logging
from threading import Lock
import re
import os


class ModemManager:
    def __init__(self):
        """
        Inisialisasi ModemManager. Hanya menyiapkan konfigurasi,
        tidak langsung membuat koneksi.
        """
        self.lock = Lock()
        self.port = os.environ.get('SERIAL_PORT')
        self.baudrate = int(os.environ.get('BAUDRATE', 115200))

        if not self.port:
            raise ValueError("Environment variable SERIAL_PORT harus diatur!")

        self.ser = None  # Koneksi serial diinisialisasi sebagai None

    @property
    def is_connected(self):
        """Property untuk memeriksa status koneksi dengan mudah."""
        return self.ser is not None and self.ser.is_open

    def connect(self):
        """
        Mencoba untuk membuat dan mengkonfigurasi koneksi serial ke modem.
        Mengembalikan True jika berhasil, False jika gagal.
        """
        if self.is_connected:
            return True
        try:
            logging.info(f"Mencoba terhubung ke port serial {self.port}...")
            self.ser = serial.Serial(self.port, self.baudrate, timeout=5)
            time.sleep(1)
            if 'OK' in self.send_at_command('AT', delay=1):
                self.send_at_command('ATE0')
                logging.info("Modem berhasil terhubung dan siap digunakan.")
                return True
            else:
                self.close()
                return False
        except serial.SerialException as e:
            logging.error(f"Gagal terhubung ke port: {e}")
            self.ser = None
            return False

    def reconnect(self):
        """Mencoba menutup koneksi lama dan membuat koneksi baru."""
        logging.warning("Mencoba menyambung kembali ke modem...")
        self.close()
        # Cukup panggil connect() yang sudah memiliki logika lengkap
        return self.connect()

    def close(self):
        """Menutup koneksi serial jika sedang terbuka."""
        if self.ser:
            try:
                if self.ser.is_open:
                    with self.lock:
                        self.ser.close()
            except Exception as e:
                logging.error(f"Error saat menutup port serial: {e}")
            finally:
                self.ser = None

    def send_at_command(self, command, delay=1):
        """Mengirim perintah AT dengan aman."""
        if not self.is_connected:
            raise serial.SerialException("Koneksi ke modem tidak aktif.")

        with self.lock:
            self.ser.write((command + '\r').encode())
            time.sleep(delay)
            return self.ser.read_all().decode()

    def send_sms(self, phone_number, message):
        """Mengirim SMS dan mengembalikan True jika berhasil, False jika gagal."""
        logging.info(f"Mengirim SMS ke {phone_number}")
        try:
            self.send_at_command('AT+CMGF=1')
            self.send_at_command(f'AT+CMGS="{phone_number}"')

            with self.lock:
                self.ser.write((message + '\x1A').encode())
                time.sleep(3)
                response = self.ser.read_all().decode()

            if '+CMGS' in response:
                logging.info("SMS berhasil dikirim.")
                return True
            else:
                logging.error(f"Gagal mengirim SMS. Respons modem: {response.strip()}")
                return False
        except serial.SerialException as e:
            logging.error(f"Gagal mengirim SMS karena error koneksi modem: {e}")
            return False

    def check_new_sms_events(self):
        """Membaca buffer serial dengan aman."""
        if not self.is_connected:
            raise serial.SerialException("Koneksi ke modem tidak aktif untuk cek event.")
        with self.lock:
            return self.ser.read_all().decode()

    def delete_sms(self, index):
        self.send_at_command(f'AT+CMGD={index}')

    def read_all_sms(self):
        self.send_at_command('AT+CMGF=1')
        response = self.send_at_command('AT+CMGL="ALL"', delay=5)
        messages = []
        pattern = re.compile(r'\+CMGL: (\d+),"(?:REC UNREAD|REC READ)","([^"]+)",[^,]*,"([^"]+)"\r?\n(.*?)\r?\n')
        matches = pattern.finditer(response)
        for match in matches:
            messages.append(
                {'index': match.group(1), 'sender': match.group(2).replace('+', ''), 'timestamp': match.group(3),
                 'content': match.group(4).strip()})
        if messages: logging.info(f"Ditemukan {len(messages)} pesan baru.")
        return messages

    def enable_new_sms_notifications(self):
        self.send_at_command('AT+CNMI=2,1,0,0,0')

    def get_signal_quality(self):
        response = self.send_at_command("AT+CSQ", delay=2)
        match = re.search(r'\+CSQ:\s*(\d+),(\d+)', response)
        if match:
            rssi = int(match.group(1))
            if rssi == 99: return "Sinyal tidak diketahui atau tidak ada."
            strength_percent = (rssi / 31) * 100
            return f"Kualitas Sinyal: {rssi} ({strength_percent:.0f}%)"
        return "Gagal mendapatkan info sinyal."

    def get_network_registration(self):
        response = self.send_at_command("AT+CREG?", delay=2)
        match = re.search(r'\+CREG:\s*\d,(\d)', response)
        if match:
            status_code = int(match.group(1))
            statuses = {0: "Tidak terdaftar, modem tidak mencari.", 1: "Terdaftar di jaringan utama.",
                        2: "Tidak terdaftar, modem mencari.", 3: "Pendaftaran ditolak.", 4: "Status tidak diketahui.",
                        5: "Terdaftar, roaming."}
            return f"Status Jaringan: {statuses.get(status_code, 'Kode tidak dikenal.')}"
        return "Gagal mendapatkan status registrasi."

    def get_sim_pin_status(self):
        response = self.send_at_command("AT+CPIN?", delay=2)
        if "+CPIN: READY" in response: return "Status SIM: READY (Siap digunakan)."
        match = re.search(r'\+CPIN:\s*(\w+)', response)
        if match: return f"Status SIM: {match.group(1)}"
        return "Gagal mendapatkan status SIM."

    def get_operator_name(self):
        response = self.send_at_command("AT+COPS?", delay=3)
        match = re.search(r'\+COPS:\s*\d,\d,"([^"]+)"', response)
        if match: return f"Operator: {match.group(1)}"
        return "Gagal mendapatkan nama operator."

    def make_voice_call(self, phone_number):
        if not phone_number or not phone_number.isdigit(): return "Nomor telepon untuk panggilan tidak valid."
        logging.info(f"Melakukan panggilan ke {phone_number}")
        response = self.send_at_command(f"ATD{phone_number};", delay=5)
        if "OK" in response: return f"Berhasil memulai panggilan ke {phone_number}."
        return "Gagal melakukan panggilan."

    def hangup_call(self):
        logging.info("Mengakhiri panggilan...")
        response = self.send_at_command("ATH", delay=2)
        if "OK" in response: return "Panggilan berhasil diakhiri."
        return "Gagal mengakhiri panggilan atau tidak ada panggilan aktif."