FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 POCZTA_DANE=/dane TZ=Europe/Warsaw

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

RUN useradd -u 1000 -m poczta && mkdir -p /dane && chown -R poczta:poczta /dane /app
USER poczta

EXPOSE 8091
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8091/healthz').read()"

# Jeden worker: przebieg wysyłkowy musi żyć w pojedynczym procesie, inaczej
# każdy worker brałby tę samą paczkę listów z kolejki i wysyłał ją równolegle.
CMD ["gunicorn", "-b", "0.0.0.0:8091", "-w", "1", "--threads", "4", "--timeout", "120", "app:app"]
