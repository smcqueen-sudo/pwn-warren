FROM python:3.12-slim

# gosu lets the entrypoint drop from root to the `burrow` user after planting
# the flag. GNU tar (the vulnerable component) ships in the base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask==3.0.3

# Low-privilege user that the Flask app runs as. The home dir is root-owned 755
# so the planted flag (444, root:root) is readable but not destroyable.
RUN useradd --create-home --home-dir /home/burrow burrow \
    && chown root:root /home/burrow \
    && chmod 755 /home/burrow

# Parent dirs for per-session upload/backup state. The app creates a subdir per vistor
RUN mkdir -p /app/uploads /app/backups \
    && chown -R burrow:burrow /app/uploads /app/backups

COPY app.py /app/app.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
