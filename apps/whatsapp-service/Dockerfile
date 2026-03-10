FROM node:20-slim

# Install Chromium dependencies untuk puppeteer (dipakai oleh whatsapp-web.js)
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-sandbox \
    fonts-noto \
    fonts-noto-cjk \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Set environment variable agar puppeteer menggunakan chromium yang sudah terinstall
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install --production

# Copy source code
COPY src/ ./src/

# Buat direktori untuk session auth
RUN mkdir -p /app/.wwebjs_auth

EXPOSE 3001

CMD ["node", "src/index.js"]
