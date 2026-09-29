FROM python:3.12-slim

# Environment settings
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8080

WORKDIR /app

# Install system dependencies for PostgreSQL client and C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and models
COPY backend/ ./backend/
COPY ml/ ./ml/
COPY configs/ ./configs/
COPY schemas/ ./schemas/
COPY src/ ./src/

EXPOSE 8080

CMD exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}
