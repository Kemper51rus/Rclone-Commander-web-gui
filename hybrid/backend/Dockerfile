FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash curl inotify-tools rclone \
    && rm -rf /var/lib/apt/lists/*

COPY hybrid/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY hybrid/backend/app /app/app
COPY scripts/rclone-watch-hybrid.sh /usr/local/bin/rclone-watch-hybrid.sh
RUN chmod 755 /usr/local/bin/rclone-watch-hybrid.sh
RUN mkdir -p /app/data

ENV APP_ROOT=/app
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
