'use strict';

const express = require('express');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

// --- Konfigurasi ---
const PORT = process.env.PORT || 3001;

// --- State management ---
let clientStatus = 'initializing'; // initializing | qr | connecting | connected | disconnected
let currentQr = null;
let clientInfo = null;

// --- Inisialisasi WhatsApp Client ---
const client = new Client({
    authStrategy: new LocalAuth({ dataPath: '/app/.wwebjs_auth' }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

// --- Event Handlers WhatsApp Client ---
client.on('qr', (qr) => {
    clientStatus = 'qr';
    currentQr = qr;
    console.log('[WA] QR Code baru diterima. Scan dengan WhatsApp Anda:');
    qrcode.generate(qr, { small: true });
});

client.on('authenticated', () => {
    clientStatus = 'connecting';
    currentQr = null;
    console.log('[WA] Berhasil terautentikasi.');
});

client.on('ready', () => {
    clientStatus = 'connected';
    clientInfo = client.info;
    console.log(`[WA] Client siap! Terhubung sebagai: ${client.info.pushname} (${client.info.wid.user})`);
});

client.on('disconnected', (reason) => {
    clientStatus = 'disconnected';
    clientInfo = null;
    console.log(`[WA] Client terputus: ${reason}. Mencoba inisialisasi ulang...`);
    setTimeout(() => client.initialize(), 5000);
});

client.on('auth_failure', (msg) => {
    clientStatus = 'disconnected';
    console.error(`[WA] Autentikasi gagal: ${msg}`);
});

// --- Inisialisasi Client ---
console.log('[WA] Memulai WhatsApp client...');
client.initialize();

// --- Inisialisasi Express ---
const app = express();
app.use(express.json());

// Logging middleware
app.use((req, res, next) => {
    console.log(`[HTTP] ${req.method} ${req.path}`);
    next();
});

// --- Endpoints ---

/**
 * GET /ping
 * Health check endpoint
 */
app.get('/ping', (req, res) => {
    res.json({ status: 'ok', service: 'whatsapp-service', uptime: process.uptime() });
});

/**
 * GET /api/status
 * Cek status koneksi WhatsApp
 */
app.get('/api/status', (req, res) => {
    const response = {
        status: clientStatus,
        user: clientInfo ? {
            name: clientInfo.pushname,
            number: clientInfo.wid ? clientInfo.wid.user : null
        } : null
    };

    if (clientStatus === 'qr' && currentQr) {
        response.qr = currentQr;
    }

    res.json(response);
});

/**
 * POST /api/send
 * Kirim pesan WhatsApp
 * Body: { chatId: "628xxx@c.us", text: "pesan" }
 */
app.post('/api/send', async (req, res) => {
    const { chatId, text } = req.body;

    if (!chatId || !text) {
        return res.status(400).json({
            status: 'error',
            message: 'Field chatId dan text wajib diisi.'
        });
    }

    if (clientStatus !== 'connected') {
        return res.status(503).json({
            status: 'error',
            message: `WhatsApp client belum siap. Status saat ini: ${clientStatus}`
        });
    }

    try {
        await client.sendMessage(chatId, text);
        console.log(`[WA] Pesan terkirim ke: ${chatId}`);
        res.json({ status: 'success', message: 'Pesan berhasil dikirim.' });
    } catch (error) {
        console.error(`[WA] Gagal mengirim pesan ke ${chatId}:`, error.message);
        res.status(500).json({
            status: 'error',
            message: `Gagal mengirim pesan: ${error.message}`
        });
    }
});

// --- Start Server ---
app.listen(PORT, () => {
    console.log(`[HTTP] WhatsApp Service berjalan di port ${PORT}`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
    console.log('[APP] Menerima SIGTERM. Menutup koneksi...');
    await client.destroy();
    process.exit(0);
});

process.on('SIGINT', async () => {
    console.log('[APP] Menerima SIGINT. Menutup koneksi...');
    await client.destroy();
    process.exit(0);
});
