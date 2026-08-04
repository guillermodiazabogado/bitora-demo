FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" --uid 10001 bitora \
    && mkdir -p /bitora/storage /bitora/backups /bitora/logs \
    && chown -R bitora:bitora /app /bitora

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=bitora:bitora . .

USER bitora
EXPOSE 8787

CMD ["python", "backend/app.py"]
