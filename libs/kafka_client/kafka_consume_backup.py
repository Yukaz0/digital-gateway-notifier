import re
import time
from confluent_kafka import Consumer, KafkaException, KafkaError
import json
import logging
import os


class KafkaAlarmConsumer:
    def __init__(self, db_manager, telegram_notifier, whatsapp_notifier):
        """
        Inisialisasi Consumer. Menerima semua notifier yang dibutuhkan.
        """
        self.db_manager = db_manager
        # self.modem_manager = modem_manager
        self.telegram_notifier = telegram_notifier
        self.whatsapp_notifier = whatsapp_notifier

        bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS')
        topic = os.environ.get('KAFKA_TOPIC')
        group_id = os.environ.get('ALARM_KAFKA_GROUP_ID')
        kafka_user = os.environ.get('KAFKA_USERNAME')
        kafka_password = os.environ.get('KAFKA_PASSWORD')

        if not all([bootstrap_servers, topic, group_id]):
            raise ValueError("Konfigurasi Kafka Consumer (SERVERS, TOPIC, GROUP_ID) tidak lengkap.")

        config = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest'
        }

        if kafka_user and kafka_password:
            config.update({
                'security.protocol': 'SASL_PLAINTEXT',
                'sasl.mechanisms': 'PLAIN',
                'sasl.username': kafka_user,
                'sasl.password': kafka_password
            })

        self.topics = [t.strip() for t in topic.split(',')]
        self.consumer = Consumer(config)
        self.consumer.subscribe(self.topics)
        logging.info(f"Confluent Kafka Consumer berhasil terhubung dan subscribe ke topics: {self.topics}")

    def start_consuming(self):
        """Loop utama, mengirim notifikasi berdasarkan preferensi pelanggan."""
        logging.info("Memulai loop Kafka Alarm Consumer...")
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None: continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logging.error(f"Error Kafka Consumer: {msg.error()}")
                        break

                try:
                    alarm_data = json.loads(msg.value().decode('utf-8'))
                    logging.info(f"Menerima pesan dari Kafka: {alarm_data}")

                    # 1. Validasi pesan alarm
                    if alarm_data.get('type') != 'alarm' or not alarm_data.get('priority'):
                        logging.info(
                            "Pesan diterima bukan tipe 'alarm' atau tidak memiliki prioritas. Pesan diabaikan.")
                        continue

                    sms_message = alarm_data.get('msg')
                    priority_str = alarm_data.get('priority', "")

                    try:
                        priority_level = int(re.search(r'\d+', priority_str).group())
                    except (AttributeError, ValueError):
                        logging.warning(f"Format prioritas tidak valid: '{priority_str}'. Pesan dilewati.")
                        continue

                    if not sms_message:
                        logging.warning("Pesan alarm tidak memiliki field 'msg'. Pesan dilewati.")
                        continue

                    # 2. Ambil daftar penerima yang berhak berdasarkan prioritas
                    recipients = self.db_manager.get_recipients_by_priority(priority_level)

                    if not recipients:
                        logging.warning(
                            f"Tidak ada pelanggan yang memenuhi syarat untuk menerima alarm prioritas {priority_level}.")
                        continue

                    logging.info(
                        f"Mendeteksi alarm P-{priority_level}. Memproses notifikasi untuk {len(recipients)} penerima...")

                    # 3. Kirim notifikasi ke setiap penerima sesuai preferensinya
                    for recipient in recipients:
                        phone_number = recipient.get("phone_number")
                        if not phone_number:
                            continue

                        # Siapkan pesan untuk saluran digital (bisa lebih detail)
                        digital_message = (
                            f"🚨 *ALARM NOTIFICATION* 🚨\n\n"
                            f"*Priority:* `{priority_str}`\n"
                            f"*Message:* {sms_message}\n"
                            f"*Tag:* `{alarm_data.get('tag', 'N/A')}`"
                        )

                        sent_via_digital = False

                        # Kirim ke WhatsApp jika diaktifkan
                        if recipient.get("whatsapp"):
                            logging.info(f"Mengirim notifikasi ke {phone_number} via WhatsApp...")
                            self.whatsapp_notifier.send_message(phone_number, digital_message)
                            sent_via_digital = True

                        # Kirim ke Telegram jika diaktifkan
                        if recipient.get("telegram"):
                            logging.info(f"Mengirim notifikasi ke {phone_number} via Telegram...")
                            # Asumsi: telegram_notifier.send_message() bisa menangani pengiriman
                            self.telegram_notifier.send_message(digital_message)
                            sent_via_digital = True

                        # Jika tidak ada saluran digital yang aktif, baru kirim SMS
                        if not sent_via_digital and recipient.get("sms"):
                            logging.info(f"Mengirim notifikasi ke {phone_number} via SMS...")
                            self.modem_manager.send_sms(phone_number, sms_message)

                        time.sleep(1)

                    logging.info(f"Pengiriman notifikasi untuk alarm prioritas {priority_level} selesai.")

                except Exception as e:
                    logging.error(f"Error memproses pesan alarm: {e}", exc_info=True)

        except KeyboardInterrupt:
            logging.info("Menghentikan consumer...")
        finally:
            self.close()

    def close(self):
        if self.consumer:
            self.consumer.close()
            logging.info("Koneksi Kafka consumer ditutup.")