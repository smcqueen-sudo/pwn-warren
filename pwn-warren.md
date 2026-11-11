# Pwn-Warren — implementation brief

A self-hosted, LAN-playable **capture-the-flag lab**. One host runs several
intentionally-vulnerable web apps ("burrows"). Players on the same network
exploit each burrow, land code execution, read a flag out of a user's home
directory, and submit it to a scoreboard. Most flags captured wins.

This document is the spec. Hand it to Claude Code (or build it by hand) to
produce a `git clone … && ./init.sh && docker compose up` repo.

> **Safety (read first).** This project is, by design, a pile of remote code
> execution. Run it only on a **trusted LAN or a VPN** — never bound to a
> public IP. See the Safety section at the bottom.

---

## 1. Goal

- Host on a VM or a spare machine on a network.
- Other people on that network attack it and try to grab as many flags as
  possible.
- A scorekeeper manages teams; teams log in and submit flags; everyone can
  watch a live leaderboard.
- Casual/friendly setting — we are **not** engineering against cheating or
  collusion. Keep anti-cheat effort near zero.

## 2. Core mechanic — why reading the flag works

Each burrow runs its web app as its **own dedicated low-privilege user**
(call it `burrow` inside each container). That user's home directory holds the
flag:

```
/home/burrow/flag.txt      # owned root:root, mode 444
/home/burrow/              # owned root:root, mode 755
```

When a player exploits the burrow and pops a shell, that shell runs as
`burrow`, so `cat /home/burrow/flag.txt` works. The flag file is root-owned and
read-only, and the home dir isn't writable by `burrow`, so a player can **read**
the flag but can't delete it or grief it for everyone else. Each burrow is its
own container, so popping burrow 1 tells you nothing about burrow 2's flag.

The intended win condition per burrow is: find the vuln → get code execution
(usually a reverse shell) → read the flag → submit it.

## 3. Architecture

- **Docker Compose**, one container per burrow + one scoreboard container.
- Ports published on `0.0.0.0` so the whole LAN can reach them (this is the
  point; see Safety).
- Teardown is `docker compose down -v`. No pollution of the host.

Port map:

| Service      | Host port | Role                    |
|--------------|-----------|-------------------------|
| scoreboard   | 8000      | infrastructure (hardened, **not** a target) |
| burrow1      | 8001      | target                  |
| burrow2      | 8002      | target                  |
| burrow3      | 8003      | target                  |

Players browse to `http://<host-lan-ip>:800X`.

**Reverse shells across the LAN:** each player runs their own listener
(`nc -lvnp 4444`) on their *own* machine; the payload connects back to
`<player-ip>:4444`. Containers egress via the host by NAT, so a shell will
leave the container and reach the player's box fine. The only gotcha is the
*player's own* firewall must accept their listener port. No special Docker
networking needed (bridge + published ports is enough).

> Optional alternative: if you'd rather have the classic "one shared VM, several
> real Linux users, lateral-movement possible" flavor, provision it with a
> Vagrantfile / cloud-init that runs a host-mutating setup script **inside a
> throwaway VM**. The container model below is simpler and cleaner to reset, so
> that's the default.

## 4. Flags: generated at setup, never committed

The repo must **not** contain the flags (otherwise players just `grep` the
source). A host-side script generates random flags at setup time:

- `init.sh` (run once, before `docker compose up`):
  - generates a random flag per burrow, e.g. `flag{burrow1_<12 hex>}`
  - writes `burrows/<burrow>/.flag.env` containing just `FLAG=flag{...}` —
    **each burrow only ever receives its own flag**
  - writes `scoreboard/seed/challenges.json` — the full registry the scoreboard
    loads (id, display name, flag, points)
- `.gitignore` excludes `burrows/*/.flag.env` and
  `scoreboard/seed/challenges.json`.

Registry format (`challenges.json`):

```json
[
  {"id": "burrow1", "name": "Burrow 1 - Network Tools",  "flag": "flag{...}", "points": 100},
  {"id": "burrow2", "name": "Burrow 2 - Greeting Cards",  "flag": "flag{...}", "points": 150},
  {"id": "burrow3", "name": "Burrow 3 - Session Vault",   "flag": "flag{...}", "points": 200}
]
```

**Important:** each burrow must receive *only* its own flag. Do **not** mount
the full `challenges.json` into the burrow containers, or a player who pops one
burrow can read every flag. The full registry lives only in the (non-target)
scoreboard.

## 5. The burrows (challenges)

Three to start, each a small Flask app (~40–60 lines) with exactly one planted
vuln. Each is independent. Easy to add more later.

| id      | Theme            | Planted vulnerability           | Intended path                       |
|---------|------------------|---------------------------------|-------------------------------------|
| burrow1 | "Network Tools"  | OS command injection            | inject shell metachars into a `ping` field → reverse shell |
| burrow2 | "Greeting Cards" | Jinja2 SSTI                     | `{{ ... }}` payload rendered server-side → RCE → reverse shell |
| burrow3 | "Session Vault"  | Insecure deserialization (pickle)| craft a malicious `prefs` cookie unpickled on the server → RCE |

Vuln sketches (deliberately insecure — that's the point):

- **burrow1:** a form posts `host`; server runs `os.popen("ping -c 1 " + host)`.
  Unsanitized concatenation into a shell command → `; bash -i >& /dev/tcp/…`.
- **burrow2:** a `name` query param is concatenated into a Jinja2 template
  string and rendered: `Template("Hello " + name).render()`. Classic SSTI;
  escape to `os` via the usual gadget chain.
- **burrow3:** a `prefs` cookie (base64) is `pickle.loads`-ed on every request.
  A pickle with a `__reduce__` that calls `os.system(...)` runs on unpickle.

### Burrow container requirements

Each burrow dir has `Dockerfile`, `app.py`, `entrypoint.sh`.

- Base `python:3.12-slim`; `pip install flask==3.0.3`; app listens on
  `0.0.0.0:5000` (mapped to the host port in compose).
- Create the `burrow` user; make `/home/burrow` **root-owned 755**.
- `gosu` installed for privilege drop. (burrow1 also needs `iputils-ping`.)
- The entrypoint plants the flag as root, then drops to `burrow` and scrubs the
  flag from the environment so it can't be read back from `/proc/<pid>/environ`
  after exploitation:

```sh
#!/bin/sh
set -e
: "${FLAG:?FLAG not set - run ./init.sh then docker compose up}"
echo "$FLAG" > /home/burrow/flag.txt
chown root:root /home/burrow/flag.txt
chmod 444 /home/burrow/flag.txt
exec env -u FLAG gosu burrow python /app/app.py
```

The app process therefore runs as `burrow`, which is what makes the popped
shell able to read (but not destroy) the flag.

## 6. The scoreboard

A separate container that is **infrastructure, not a challenge** — keep it
reasonably hardened (parameterized queries, autoescaped templates, hashed team
passwords). If the scoreboard is poppable the event is pointless.

Stack: Flask + SQLite. Server-rendered HTML, no JS framework needed.

**Features**

- **Public leaderboard** (`/`, no auth): rank, team, flags captured / total,
  score. This is the always-open view.
- **Scorekeeper/admin** (password from `ADMIN_PASSWORD` env):
  - add a team (name + password)
  - remove a team (cascades to their solves)
  - see all teams with scores
- **Team**: log in with team name + password; submit flags; see which burrows
  they've captured and their score.

**Data model**

```
teams(id PK, name UNIQUE, password_hash, created)
challenges(id PK, name, flag, points)
solves(team_id, challenge_id, ts, PRIMARY KEY(team_id, challenge_id))  -- dedupe
```

**Scoring**: flat points per challenge. A flag scores once per team (the solves
PK enforces dedupe; a repeat submit says "already captured"). Leaderboard =
`SUM(points)` per team, ordered by score desc, tiebreak on earliest last-solve
time.

**Seeding**: on first boot, if `challenges` is empty, load
`/seed/challenges.json` (mounted read-only from `scoreboard/seed/`). Persist the
DB to a named volume (`/data/scoreboard.db`) so scores survive restarts.

**Flag validation** is a straight lookup: submitted string == a challenge's
`flag`. Flags are the same for every team (shared) — fine for casual play.

Routes to implement: `/`, `/login`, `/logout`, `/play`, `/submit` (POST),
`/admin/login`, `/admin`, `/admin/teams` (POST add),
`/admin/teams/<id>/delete` (POST), `/admin/logout`.

## 7. Reset (recover from tampering)

A player with a shell can delete a flag, kill the service, or patch the vuln.
`scripts/reset.sh` restores the burrows **without rotating flags and without
touching the scoreboard**:

- Each burrow re-reads its flag from its `.flag.env` on boot and re-plants it,
  so a plain `docker compose up -d --force-recreate <burrows>` restores the
  original, still-valid flags.
- The scoreboard is deliberately excluded — you never wipe scores mid-event.
- **Never regenerate flags mid-event.** If `init.sh` made new random flags, every
  already-submitted flag would go stale. Reset re-applies the *same* flags.
- Optional cron for periodic auto-reset:
  `*/15 * * * * cd /path/to/pwn-warren && scripts/reset.sh >> /var/log/pwn-warren-reset.log 2>&1`

## 8. Repo layout

```
pwn-warren/
├── README.md                 # overview + safety + run steps
├── docker-compose.yml        # 0.0.0.0 bindings; scoreboard on a volume
├── init.sh                   # generate flags → .flag.env + challenges.json (run once)
├── .env.example              # ADMIN_PASSWORD, optional SECRET_KEY
├── .gitignore                # ignores .flag.env and challenges.json
├── burrows/
│   ├── burrow1-cmdinjection/ # Dockerfile, app.py, entrypoint.sh
│   ├── burrow2-ssti/
│   └── burrow3-deserialize/
├── scoreboard/
│   ├── Dockerfile
│   ├── app.py
│   ├── requirements.txt
│   ├── templates/            # base, index(leaderboard), login, play, admin, admin_login
│   └── seed/                 # challenges.json lands here (gitignored)
├── scripts/
│   └── reset.sh
└── solutions/
    └── README.md             # intended exploit walkthrough per burrow (keep out of players' way)
```

## 9. Setup & run

```bash
git clone <repo> && cd pwn-warren
./init.sh                         # generates the flags (run once)
export ADMIN_PASSWORD=<something>  # scoreboard admin login
docker compose up --build
```

Then: open the scorekeeper panel at `http://<host>:8000/admin/login`, add
teams, and share `http://<host>:8000` with players as the leaderboard + submit
portal. Targets are on `:8001`–`:8003`.

## 10. Safety

- **LAN or VPN only. Never a public IP.** These are intentional RCE services; on
  the open internet they're co-opted within hours. If the host is a cloud VM,
  lock the security group to player source IPs or a VPN.
- On Ubuntu, **Docker writes its own iptables rules and can bypass `ufw`** —
  published ports may be reachable even when `ufw` looks like it's blocking
  them. Don't rely on `ufw` alone to fence this off; control exposure at the
  network/security-group level.
- Flags are generated at setup and gitignored, so the repo ships the
  vulnerabilities, not the answers.
- Flags are root-owned `444` with a root-owned home dir so players can read but
  not destroy them; `scripts/reset.sh` rolls back any other tampering.

## 11. Naming

Project: **Pwn Warren** (repo slug `pwn-warren`). Challenges are "burrows"
(`burrow1`, `burrow2`, …) — the rabbit-warren/down-the-rabbit-hole theme.

## 12. Suggested build order (for Claude Code)

1. Scaffold the tree, `docker-compose.yml`, `init.sh`, `scripts/reset.sh`,
   `.gitignore`, `.env.example`.
2. Build the three burrows (Dockerfile + app + entrypoint each); confirm the
   flag-planting + priv-drop pattern.
3. Build the scoreboard (schema, seeding, routes, templates).
4. `README.md` with the safety warnings baked in, and `solutions/` writeups.
5. `git init` + first commit. (Don't commit `.flag.env` or `challenges.json`.)
6. Smoke test: `./init.sh && docker compose up --build`, add a team, exploit
   burrow1, submit its flag, watch the leaderboard update; run `reset.sh` and
   confirm the same flag still validates.

## 13. Possible extensions

- **More burrows / vuln classes:** unrestricted file upload → webshell;
  SQL injection → creds/RCE; path traversal / LFI (note: an LFI that reads
  files as the `burrow` user grabs the flag with no shell — a nice "not every
  box needs a reverse shell" lesson); XXE → file read; a pinned outdated
  component with a known CVE.
- **Dynamic scoring** (points decay as more teams solve) and **first-blood
  bonuses** — CTFd-style.
- **Drop-in CTFd instead of the custom scoreboard** if you ever want teams,
  categories, hints, and dynamic scoring for free (it's a bigger Flask app; the
  custom one stays lean).
- **Per-team flag instancing** if the event ever gets competitive enough that
  flag-sharing matters (materially more complex — needs per-team instances).
