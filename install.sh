#!/bin/bash
# Skrip ini mengotomatiskan proses setup dan menjalankan aplikasi SMS Gateway.
# Menggunakan Python virtual environment (venv).

set -e  # Hentikan jika ada kesalahan

VENV_DIR="venv"  # Nama folder virtual environment

# --- Langkah 1: Memeriksa Instalasi Python ---
echo "🔎 Mengecek instalasi Python 3..."

if command -v python3 &> /dev/null
then
    echo "✅ Python 3 sudah terinstal."
else
    echo "⚠ Python 3 tidak ditemukan. Mencoba menginstal..."
    if command -v apt-get &> /dev/null
    then
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv
        echo "✅ Python 3, pip, dan venv berhasil diinstal."
    else
        echo "❌ Tidak dapat menemukan package manager 'apt-get'. Silakan instal Python 3 secara manual."
        exit 1
    fi
fi

# --- Langkah 2: Membuat dan Mengaktifkan Virtual Environment ---
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Membuat virtual environment di folder '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
fi

echo "🔌 Mengaktifkan virtual environment..."
source "$VENV_DIR/bin/activate"

# --- Langkah 3: Menginstal Dependensi ---
echo "🚀 Menginstal dependensi dari requirements.txt ke dalam venv..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependensi berhasil diinstal."

# --- Langkah 4: Menjalankan Aplikasi ---
echo "🚀 Menjalankan aplikasi utama (main.py)..."
python main.py

# Opsional: Menonaktifkan venv setelah selesai
# deactivate