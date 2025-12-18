from flask import Flask, request, jsonify
import logging
import os


def create_flask_app(modem_manager):
    app = Flask(__name__)

    api_key = os.environ.get('API_KEY')
    if not api_key:
        raise ValueError("Environment variable API_KEY tidak diatur! API tidak bisa berjalan dengan aman.")

    @app.route('/kirim_atcmd', methods=['POST'])
    def kirim_atcmd():
        provided_key = request.headers.get('X-API-KEY')

        if not provided_key or provided_key != api_key:
            logging.warning("Upaya akses API tidak sah.")
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

        data = request.json
        if not data or 'phone_number' not in data or 'command' not in data:
            return jsonify({'status': 'error', 'message': 'Payload tidak valid'}), 400

        try:
            sukses = modem_manager.send_sms(data['phone_number'], data['command'])
            if sukses:
                return jsonify({'status': 'success', 'message': 'SMS berhasil dikirim'}), 200
            else:
                return jsonify({'status': 'error', 'message': 'Gagal mengirim SMS dari modem'}), 500
        except Exception as e:
            logging.error(f"Flask API gagal mengirim command: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return app