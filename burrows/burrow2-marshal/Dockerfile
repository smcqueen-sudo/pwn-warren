FROM ruby:3.2-slim

# gosu lets the entrypoint drop from root to the `burrow` user after planting
# the flag.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Sinatra 4 runs on Rack 3. Use the pure-Ruby WEBrick server (no native
# extensions, so this builds on the slim image with no C toolchain). Pinned for
# reproducible builds.
RUN gem install --no-document sinatra -v 4.1.1 \
    && gem install --no-document rackup -v 2.2.1 \
    && gem install --no-document webrick -v 1.8.1

# Low-privilege user that the app runs as. The home dir is root-owned 755 so the
# planted flag (444, root:root) is readable but not destroyable.
RUN useradd --create-home --home-dir /home/burrow burrow \
    && chown root:root /home/burrow \
    && chmod 755 /home/burrow

RUN mkdir -p /app
COPY app.rb /app/app.rb
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
