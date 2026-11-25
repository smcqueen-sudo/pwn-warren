FROM python:3.12-slim

# gosu lets the entrypoint drop from root to the `burrow` user after planting
# the flag. git is the plant-time tool: the entrypoint builds the served repo's
# history (with the freshly-generated admin token) at container start.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask==3.0.3

# Low-privilege user that the Flask app runs as. The home dir is root-owned 755
# so the planted flag (444, root:root) is readable but not destroyable.
RUN useradd --create-home --home-dir /home/burrow burrow \
    && chown root:root /home/burrow \
    && chmod 755 /home/burrow

# /srv/site is the served web root; the entrypoint builds its git history there
# at plant time. /app/site holds the static page baked into the image (the
# token-bearing config.py is generated at runtime, never shipped).
RUN mkdir -p /srv /app/site

COPY app.py /app/app.py
COPY site/index.html /app/site/index.html
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
