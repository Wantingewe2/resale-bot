FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# seen_listings.db and logs should persist across restarts - mount a volume
# at /app/data and point database_path / logging.file in config.yaml there.
VOLUME ["/app/data"]

CMD ["python", "main.py"]
