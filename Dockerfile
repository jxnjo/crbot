# Dockerfile
FROM python:3.11-alpine

# Build-Args kommen aus der GitHub Action
ARG BUILD_SHA="dev"
ARG BUILD_REF="local"
ARG BUILD_TIME="unknown"
ARG BUILD_AUTHOR="unknown"
ARG BUILD_MSG=""

# Zur Laufzeit verfügbar
ENV BOT_VERSION_SHA=$BUILD_SHA \
    BOT_VERSION_REF=$BUILD_REF \
    BOT_VERSION_TIME=$BUILD_TIME \
    BOT_VERSION_AUTHOR=$BUILD_AUTHOR \
    BOT_VERSION_MSG=$BUILD_MSG \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Systempakete (tzdata für ZoneInfo auf Alpine)
RUN apk add --no-cache tzdata

# bessere Layer-Caches: erst requirements, dann Code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "bot.py"]