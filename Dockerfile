FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" --uid 10001 bitora \
    && mkdir -p /bitora/storage /bitora/backups /bitora/logs \
    && chown -R bitora:bitora /app /bitora

COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY --chown=bitora:bitora . .

USER bitora
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/ready', timeout=4).read()" || exit 1

CMD ["python", "backend/app.py"]
