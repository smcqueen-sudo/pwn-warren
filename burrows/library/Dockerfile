FROM python:3.12-slim

# gosu lets the entrypoint drop from root to the `burrow` user after planting
# the flag.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask==3.0.3

# Low-privilege user that the Flask app runs as. The home dir is root-owned 755
# so the planted flag (444, root:root) is readable but not destroyable.
RUN useradd --create-home --home-dir /home/burrow burrow \
    && chown root:root /home/burrow \
    && chmod 755 /home/burrow

# The library's legitimate documents. The path-traversal vuln lets a player
# escape this directory to read arbitrary files (e.g. the flag).
RUN mkdir -p /app/docs \
    && printf 'Welcome to the Burrow Library.\nBrowse our collection from the home page.\n' > /app/docs/welcome.txt \
    && printf 'The warren rules: be kind, share carrots, read quietly.\n' > /app/docs/rules.txt \
    && printf 'Chapter 1: Down the hole we go...\n' > /app/docs/story.txt

COPY app.py /app/app.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
