# syntax=docker/dockerfile:1
# SPDX-License-Identifier: Apache-2.0
FROM python:3.13-slim

LABEL org.opencontainers.image.title="Sharewerk" \
      org.opencontainers.image.description="Turn Instagram and Facebook posts into share-ready packs" \
      org.opencontainers.image.source="https://github.com/Azentrius/sharewerk" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin sharewerk

WORKDIR /srv/sharewerk
COPY requirements.txt .
# --upgrade so every build gets the newest gallery-dl / yt-dlp
RUN pip install --upgrade -r requirements.txt

COPY app ./app
COPY LICENSE NOTICE README.md ./
COPY LICENSES ./LICENSES

# Everything that is written at runtime lives in /data (models, caches, jobs).
ENV SHAREWERK_DATA_DIR=/data \
    HF_HOME=/data/models/hf \
    XDG_CACHE_HOME=/data/cache
RUN mkdir -p /data /secrets && chown sharewerk:sharewerk /data

USER sharewerk
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4).status == 200 else 1)"]

CMD ["python", "-m", "app.main"]
