#!/bin/sh
# Plant the flag as root, build the served repo's (leaky) git history with a
# freshly generated admin token, then drop to the low-privilege `burrow` user.
set -e

: "${FLAG:?FLAG not set - run ./init.sh then docker compose up}"

echo "$FLAG" > /home/burrow/flag.txt
chown root:root /home/burrow/flag.txt
chmod 444 /home/burrow/flag.txt

# Generate the admin token
ADMIN_TOKEN="warren-$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
export ADMIN_TOKEN

SITE=/srv/site
rm -rf "$SITE"
mkdir -p "$SITE"
cp /app/site/index.html "$SITE/index.html"

export GIT_AUTHOR_NAME="Warren Admin"   GIT_AUTHOR_EMAIL="admin@warren.lan"
export GIT_COMMITTER_NAME="Warren Admin" GIT_COMMITTER_EMAIL="admin@warren.lan"

cd "$SITE"
git init -q

# commit 1: the mistake (token hard-coded in source)
cat > config.py <<CFG
# Warren Dispatch - site configuration
# Token for the staff admin console (/admin).
# Reminder to keep your git history clean fellas :P
ADMIN_TOKEN = "$ADMIN_TOKEN"
DEBUG = False
CFG
git add index.html config.py
git commit -q -m "Launch Warren Dispatch + admin console config"

# commit 2: the "fix" (token pulled from source into an env var)
cat > config.py <<'CFG'
import os

# Warren Dispatch - site configuration
# Security: admin token moved OUT of source control (see incident #1337).
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
DEBUG = False
CFG
git add config.py
git commit -q -m "security: move admin token out of source control (#1337)"

git update-server-info
chmod -R a+rX "$SITE"

# Scrub FLAG so the app can only reach it via flag.txt; keep ADMIN_TOKEN, which
# is the intended stepping stone, not the flag itself.
exec env -u FLAG gosu burrow python /app/app.py
