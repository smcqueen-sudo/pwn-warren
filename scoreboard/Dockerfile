FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py /app/app.py
COPY templates /app/templates

# SQLite database lives on a named volume mounted here (see docker-compose.yml).
RUN mkdir -p /data

EXPOSE 5000
CMD ["python", "/app/app.py"]
