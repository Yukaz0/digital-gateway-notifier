FROM python:3.11-slim

# Install system dependencies needed by psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY apps/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY libs ./libs
COPY apps/backend ./apps/backend

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Expose the port the API will run on
EXPOSE 8000

# Command to run the Uvicorn server
CMD ["uvicorn", "apps.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
