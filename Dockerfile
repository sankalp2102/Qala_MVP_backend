FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libpq-dev gcc libmagic1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Qala/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn psycopg2-binary

COPY Qala/ .

RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["gunicorn", "Qala.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-"]
