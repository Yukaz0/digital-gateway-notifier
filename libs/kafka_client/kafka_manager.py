from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
import json
import logging
import os
import socket
import re
import time


class KafkaProducer:
    def __init__(self):
        """
        Inisialisasi Kafka Producer menggunakan confluent-kafka.
        """
        bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS')
        self.topic = os.environ.get('KAFKA_TOPIC')
        kafka_user = os.environ.get('KAFKA_USERNAME')
        kafka_password = os.environ.get('KAFKA_PASSWORD')

        if not bootstrap_servers or not self.topic:
            raise ValueError("KAFKA_BOOTSTRAP_SERVERS dan KAFKA_TOPIC harus diatur.")

        config = {
            'bootstrap.servers': bootstrap_servers,
            'client.id': socket.gethostname()
        }

        if kafka_user and kafka_password:
            logging.info("Menggunakan autentikasi SASL_PLAIN untuk Kafka.")
            config.update({
                'security.protocol': 'SASL_PLAINTEXT',
                'sasl.mechanisms': 'PLAIN',
                'sasl.username': kafka_user,
                'sasl.password': kafka_password
            })

        try:
            self.producer = Producer(config)
            logging.info(f"Confluent Kafka Producer berhasil terhubung ke {bootstrap_servers}")
        except Exception as e:
            logging.error(f"Gagal menginisialisasi Confluent Kafka Producer: {e}")
            raise

    def send_data(self, topic, data):
        """
        Mengirim data ke topic Kafka yang spesifik.
        
        Args:
            topic (str): Nama topic tujuan.
            data (dict): Data yang akan dikirim (dalam format dictionary).
        """
        def delivery_report(err, msg):
            """Callback yang dipanggil setelah pesan dikirim atau gagal."""
            if err is not None:
                logging.error(f"Gagal mengirim pesan ke topic '{topic}': {err}")
            else:
                logging.info(f"Pesan berhasil dikirim ke topic '{msg.topic()}' [partisi {msg.partition()}]")

        try:
            payload = json.dumps(data).encode('utf-8')
            self.producer.produce(topic, value=payload, callback=delivery_report)
            
            self.producer.poll(0)

        except Exception as e:
            logging.error(f"Error saat mencoba mengirim data ke Kafka: {e}")
    
    def check_status(self):
        return "Terinisialisasi" if self.producer else "Gagal"

    def close(self):
        if self.producer:
            logging.info("Menunggu semua pesan Kafka terkirim (flushing)...")
            self.producer.flush()
            logging.info("Koneksi Kafka producer ditutup.")


class KafkaAlarmConsumer:
    # Hapus telegram_bot dari __init__
    def __init__(self, db_manager, whatsapp_notifier, kafka_manager):
        """
        Inisialisasi Consumer. telegram_bot akan diatur nanti melalui set_telegram_bot.
        """
        self.db_manager = db_manager
        self.whatsapp_notifier = whatsapp_notifier
        self.kafka_producer = kafka_manager
        self.telegram_bot = None
        self.log_topic = os.environ.get('NOTIFICATION_LOGS_TOPIC')

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
            config.update({'security.protocol': 'SASL_PLAINTEXT', 'sasl.mechanisms': 'PLAIN', 'sasl.username': kafka_user, 'sasl.password': kafka_password})

        self.topics = [t.strip() for t in topic.split(',')]
        self.consumer = Consumer(config)
        self.consumer.subscribe(self.topics)
        logging.info(f"Confluent Kafka Consumer terhubung dan subscribe ke topics: {self.topics}")
        
    def set_telegram_bot(self, telegram_bot):
        """Method untuk menautkan instance TelegramBot setelah dibuat."""
        self.telegram_bot = telegram_bot
        logging.info("Telegram Bot telah ditautkan ke Kafka Consumer.")

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

                    if alarm_data.get('type') != 'alarm' or not alarm_data.get('priority'):
                        logging.info("Pesan diterima bukan tipe 'alarm' atau tidak memiliki prioritas. Pesan diabaikan.")
                        continue

                    alarm_message = alarm_data.get('msg')
                    priority_str = alarm_data.get('priority', "")
                    try:
                        priority_level = int(re.search(r'\d+', priority_str).group())
                    except (AttributeError, ValueError):
                        logging.warning(f"Format prioritas tidak valid: '{priority_str}'. Pesan dilewati.")
                        continue
                    if not alarm_message:
                        logging.warning("Pesan alarm tidak memiliki field 'msg'. Pesan dilewati.")
                        continue

                    recipients = self.db_manager.get_recipients_by_priority(priority_level)
                    if not recipients:
                        logging.warning(f"Tidak ada pelanggan yang memenuhi syarat untuk menerima alarm prioritas {priority_level}.")
                        continue
                    
                    logging.info(f"Mendeteksi alarm P-{priority_level}. Memproses notifikasi untuk {len(recipients)} penerima...")
                    for recipient in recipients:
                        phone_number = recipient.get("nomor_hp")
                        if not phone_number: continue
                        
                        digital_message = (f"🚨 *ALARM NOTIFICATION* 🚨\n\n"
                                         f"*Priority:* `{priority_str}`\n"
                                         f"*Message:* {alarm_message}\n"
                                         f"*Tag:* `{alarm_data.get('tag', 'N/A')}`")

                        if recipient.get("whatsapp"):
                            if self.whatsapp_notifier.send_message(phone_number, digital_message):
                                log = {"channel": "WhatsApp", "recipient": phone_number, "time": int(time.time() * 1000)}
                                self.kafka_producer.send_data(self.log_topic, log)
                        
                        # Cek apakah bot sudah ditautkan sebelum mengirim
                        if recipient.get("telegram") and self.telegram_bot:
                            chat_id = recipient.get("telegram_chat_id")
                            if chat_id:
                                if self.telegram_bot.send_notification(chat_id, digital_message):
                                    log = {"channel": "Telegram", "recipient": chat_id, "time": int(time.time() * 1000)}
                                    self.kafka_producer.send_data(self.log_topic, log)
                        
                        time.sleep(1)
                    logging.info(f"Pengiriman notifikasi untuk alarm prioritas {priority_level} selesai.")
                except Exception as e:
                    logging.error(f"Error memproses pesan alarm: {e}", exc_info=True)
        except KeyboardInterrupt:
            logging.info("Consumer shutdown requested...")
        finally:
            self.close()

    def check_status(self):
        """Mengembalikan status consumer."""
        # Ini adalah pemeriksaan sederhana; bisa dikembangkan untuk mengecek koneksi aktif
        return "Berjalan & Mendengarkan" if self.consumer else "Gagal"

    def close(self):
        if self.consumer:
            self.consumer.close()
            logging.info("Koneksi Kafka consumer ditutup.")