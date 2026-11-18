#!/bin/sh
# Plant the flag as root, then drop to the low-privilege `burrow` user to run the app
set -e

: "${FLAG:?FLAG not set - run ./init.sh then docker compose up}"

echo "$FLAG" > /home/burrow/flag.txt
chown root:root /home/burrow/flag.txt
chmod 444 /home/burrow/flag.txt

exec env -u FLAG gosu burrow python /app/app.py
