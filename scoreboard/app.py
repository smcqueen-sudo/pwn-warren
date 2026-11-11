"""Pwn-Warren scoreboard — infrastructure, not a target: keep it hardened
(parameterized SQL, autoescaped templates, hashed passwords).

Flask + SQLite on a named volume; seeds from /seed/challenges.json (the full
flag registry, which lives only here) on first boot.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = os.environ.get("DB_PATH", "/data/scoreboard.db")
SEED_PATH = os.environ.get("SEED_PATH", "/seed/challenges.json")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #

def get_db():
    """Return the per-request SQLite connection, opening it on first use."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they don't exist, then seed challenges on first boot."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS challenges (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            flag       TEXT NOT NULL,
            points     INTEGER NOT NULL,
            difficulty TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS solves (
            team_id      INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            challenge_id TEXT NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
            ts           TEXT NOT NULL,
            PRIMARY KEY (team_id, challenge_id)
        );
        """
    )
    db.commit()
    seed_challenges(db)
    db.close()


def seed_challenges(db):
    """Load challenges from the seed registry, but only if the table is empty."""
    already = db.execute("SELECT COUNT(*) AS n FROM challenges").fetchone()["n"]
    if already:
        return
    if not os.path.exists(SEED_PATH):
        app.logger.warning("No seed file at %s; challenges table left empty", SEED_PATH)
        return

    with open(SEED_PATH, "r", encoding="utf-8") as seed_file:
        challenges = json.load(seed_file)

    db.executemany(
        "INSERT INTO challenges (id, name, flag, points, difficulty) "
        "VALUES (:id, :name, :flag, :points, :difficulty)",
        challenges,
    )
    db.commit()
    app.logger.info("Seeded %d challenges from %s", len(challenges), SEED_PATH)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #

def list_challenges():
    """All challenges, easiest (fewest points) first."""
    return get_db().execute(
        "SELECT id, name, points, difficulty FROM challenges ORDER BY points ASC, name ASC"
    ).fetchall()


def leaderboard_rows():
    """Teams by score desc, tiebroken by earliest most-recent solve (no-solve teams last)."""
    return get_db().execute(
        """
        SELECT
            teams.id   AS id,
            teams.name AS name,
            COUNT(solves.challenge_id)              AS captured,
            COALESCE(SUM(challenges.points), 0)     AS score,
            MAX(solves.ts)                          AS last_solve
        FROM teams
        LEFT JOIN solves     ON solves.team_id = teams.id
        LEFT JOIN challenges ON challenges.id = solves.challenge_id
        GROUP BY teams.id, teams.name
        ORDER BY score DESC, (last_solve IS NULL), last_solve ASC, teams.name ASC
        """
    ).fetchall()


def solved_challenge_ids(team_id):
    rows = get_db().execute(
        "SELECT challenge_id FROM solves WHERE team_id = ?", (team_id,)
    ).fetchall()
    return {row["challenge_id"] for row in rows}


# --------------------------------------------------------------------------- #
# Auth helpers
# --------------------------------------------------------------------------- #

def current_team():
    team_id = session.get("team_id")
    if team_id is None:
        return None
    return get_db().execute(
        "SELECT id, name FROM teams WHERE id = ?", (team_id,)
    ).fetchone()


def require_admin():
    if not session.get("is_admin"):
        abort(403)


# --------------------------------------------------------------------------- #
# Public + team routes
# --------------------------------------------------------------------------- #

@app.route("/")
def index():
    challenges = list_challenges()
    return render_template(
        "index.html",
        leaderboard=leaderboard_rows(),
        challenges=challenges,
        total_challenges=len(challenges),
        team=current_team(),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        team = get_db().execute(
            "SELECT id, password_hash FROM teams WHERE name = ?", (name,)
        ).fetchone()
        if team and check_password_hash(team["password_hash"], password):
            session["team_id"] = team["id"]
            return redirect(url_for("play"))
        flash("Invalid team name or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("team_id", None)
    return redirect(url_for("index"))


@app.route("/play")
def play():
    team = current_team()
    if team is None:
        return redirect(url_for("login"))
    return render_template(
        "play.html",
        team=team,
        challenges=list_challenges(),
        solved=solved_challenge_ids(team["id"]),
    )


@app.route("/submit", methods=["POST"])
def submit():
    team = current_team()
    if team is None:
        return redirect(url_for("login"))

    challenge_id = request.form.get("challenge_id", "")
    submitted_flag = request.form.get("flag", "").strip()

    challenge = get_db().execute(
        "SELECT id, name, flag FROM challenges WHERE id = ?", (challenge_id,)
    ).fetchone()
    if challenge is None:
        flash("Unknown challenge.", "error")
        return redirect(url_for("play"))

    if submitted_flag != challenge["flag"]:
        flash(f"Incorrect flag for {challenge['name']}.", "error")
        return redirect(url_for("play"))

    # solves PK dedupes repeat captures; report the second submit as a no-op.
    db = get_db()
    existing = db.execute(
        "SELECT 1 FROM solves WHERE team_id = ? AND challenge_id = ?",
        (team["id"], challenge["id"]),
    ).fetchone()
    if existing:
        flash(f"You already captured {challenge['name']}.", "info")
    else:
        db.execute(
            "INSERT INTO solves (team_id, challenge_id, ts) VALUES (?, ?, ?)",
            (team["id"], challenge["id"], now_iso()),
        )
        db.commit()
        flash(f"Captured {challenge['name']}! \U0001f3c1", "success")
    return redirect(url_for("play"))


# --------------------------------------------------------------------------- #
# Admin routes
# --------------------------------------------------------------------------- #

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if ADMIN_PASSWORD and request.form.get("password", "") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        flash("Invalid admin password.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
def admin():
    require_admin()
    return render_template("admin.html", teams=leaderboard_rows())


@app.route("/admin/teams", methods=["POST"])
def admin_add_team():
    require_admin()
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")
    if not name or not password:
        flash("Team name and password are both required.", "error")
        return redirect(url_for("admin"))
    try:
        db = get_db()
        db.execute(
            "INSERT INTO teams (name, password_hash, created) VALUES (?, ?, ?)",
            (name, generate_password_hash(password), now_iso()),
        )
        db.commit()
        flash(f"Added team {name}.", "success")
    except sqlite3.IntegrityError:
        flash(f"A team named {name} already exists.", "error")
    return redirect(url_for("admin"))


@app.route("/admin/teams/<int:team_id>/delete", methods=["POST"])
def admin_delete_team(team_id):
    require_admin()
    db = get_db()
    # ON DELETE CASCADE removes the team's solves too (foreign_keys pragma on).
    db.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    db.commit()
    flash("Team removed.", "info")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    if not ADMIN_PASSWORD:
        raise SystemExit("ADMIN_PASSWORD is not set - refusing to start the scoreboard.")
    init_db()
    app.run(host="0.0.0.0", port=5000)
