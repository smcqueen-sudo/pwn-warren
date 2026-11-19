# Pwn Warren

A self-hosted, LAN-playable capture-the-flag lab. One host runs several
intentionally-vulnerable web apps ("burrows") plus a scoreboard. Players on the
same network exploit a burrow, read a flag out of the service user's home
directory, and submit it to the scoreboard. Most flags captured wins.

> ## ⚠️ Safety - read first
>
> This project is, by design, a pile of **remote code execution**. Run it only
> on a **trusted LAN or a VPN** - **never bound to a public IP.** On the open
> internet these services are co-opted within minutes of discovery.
>
> - On Ubuntu, Docker writes its own iptables rules and can **bypass `ufw`** -
>   published ports may be reachable even when `ufw` looks like it's blocking
>   them. Control exposure at the network / security-group level, not with
>   `ufw` alone.

## Setup & run

```bash
./init.sh                           # generate the flags (run ONCE)
export ADMIN_PASSWORD=<something>   # scoreboard admin login
docker compose up --build           # binds 0.0.0.0 so the LAN can reach it
```

Then:

- **Scorekeeper:** open `http://<host>:8000/admin/login`, add teams.
- **Players:** `http://<host>:8000` is the leaderboard + flag submission portal.
  Targets are on `:8001`+.

## What's here

| Service (name) | Port | Difficulty |
| -------------- | ---- | ---------- |
| scoreboard     | 8000 | -          |
| Burrow library | 8001 | Easy       |
| Warren Lounge  | 8002 | Medium     |
| Burrow Backup  | 8003 | Hard       |

## Housekeeping

```bash
scripts/reset.sh            # restore tampered burrows; same flags, scoreboard untouched
docker compose down -v      # full teardown (also wipes the scoreboard volume)

# recreate one burrow without touching the rest or the scoreboard:
docker compose up -d --build --force-recreate library
```

**Never run `init.sh` mid-event** - it generates new flags and invalidates every
already-submitted one. Use `scripts/reset.sh` to recover from tampering.

## Adding a burrow

Create `burrows/<burrowName>/` (Dockerfile + app.py + entrypoint.sh following
the plant-flag -> env-scrub -> `gosu burrow` pattern), add a service to
`docker-compose.yml` on port `800N`, add one row to the `BURROWS` registry in
`init.sh`, and drop a writeup in `solutions/`.
