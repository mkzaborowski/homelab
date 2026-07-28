FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 IBKR_DANE=/dane TZ=Europe/Warsaw

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

RUN useradd -u 1000 -m portfel && mkdir -p /dane && chown -R portfel:portfel /dane /app
USER portfel

EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8090/healthz').read()"

# jeden worker: harmonogram APScheduler musi żyć w pojedynczym procesie,
# inaczej pobranie z IBKR odpaliłoby się tyle razy, ile jest workerów
CMD ["gunicorn", "-b", "0.0.0.0:8090", "-w", "1", "--threads", "4", "--timeout", "180", "app:app"]
