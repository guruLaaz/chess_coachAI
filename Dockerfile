FROM python:3.12-slim

# Install Stockfish
RUN apt-get update && apt-get install -y stockfish && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default Stockfish path for Linux
ENV STOCKFISH_PATH=/usr/games/stockfish
ENV BOOK_PATH=/app/data/gm2001.bin
ENV PYTHONPATH=/app:/app/fetchers

EXPOSE 8000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
