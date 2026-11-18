import os
import re
import secrets
import subprocess

from flask import Flask, abort, make_response, redirect, request, send_file

app = Flask(__name__)

UPLOADS_ROOT = "/app/uploads"
BACKUPS_ROOT = "/app/backups"
SEED = "Carrot inventory: 42 crates.\nRemember to rotate the parsnips.\nDelete long-eli.jpg.\n"

# Ensure sid is valid, this is supposed to be a hard challenge B)
def valid_sid(sid):
    return bool(sid) and re.fullmatch('^[0-9a-f]{32}$', sid) is not None


def upload_dir(sid):
    return os.path.join(UPLOADS_ROOT, sid)


def backup_path(sid):
    return os.path.join(BACKUPS_ROOT, sid + ".tgz")


# Create a directory based on the session id if one does not exist
def ensure_dir(sid):
    d = upload_dir(sid)
    os.makedirs(d, exist_ok=True)
    seed = os.path.join(d, "notes.txt")  # so a brand-new session's `tar *` isn't empty
    if not os.path.exists(seed):
        with open(seed, "w", encoding="utf-8") as fh:
            fh.write(SEED)
    return d


@app.route("/")
def index():
    sid = request.cookies.get("sid")
    if not valid_sid(sid):
        sid = secrets.token_hex(16)
    ensure_dir(sid)

    uploads = sorted(os.listdir(upload_dir(sid)))
    items = "\n".join(f"<li>{name}</li>" for name in uploads)

    download_link = ""
    if os.path.exists(backup_path(sid)):
        download_link = '<p><a href="/download">Download latest backup</a></p>'

    html = f"""
    <h1>Burrow Backup</h1>
    <p>Files in your burrow:</p>
    <ul>{items}</ul>

    <h2>Add a file</h2>
    <form method="post" action="/upload" enctype="multipart/form-data">
      <input type="file" name="f">
      <button type="submit">Upload</button>
    </form>

    <h2>Back up</h2>
    <form method="post" action="/backup">
      <button type="submit">Back up my uploads</button>
    </form>
    {download_link}
    """

    resp = make_response(html)
    resp.set_cookie("sid", sid, httponly=True, samesite="Lax")
    return resp


@app.route("/upload", methods=["POST"])
def upload():
    sid = request.cookies.get("sid")
    if not valid_sid(sid):
        return redirect("/")
    d = ensure_dir(sid)

    f = request.files["f"]
    # For those curious, a potential fix to this exploit could be doing:
    # `secure_filename(f.filename)` here instead :D
    name = os.path.basename(f.filename)
    f.save(os.path.join(d, name))
    return redirect("/")


@app.route("/backup", methods=["POST"])
def backup():
    sid = request.cookies.get("sid")
    if not valid_sid(sid):
        return redirect("/")
    d = ensure_dir(sid)

    # backup_path(sid) is safe to interpolate: valid_sid guarantees pure hex
    subprocess.run(f"tar czf {backup_path(sid)} *", shell=True, cwd=d)
    return redirect("/")


@app.route("/download")
def download():
    sid = request.cookies.get("sid")
    if valid_sid(sid) and os.path.exists(backup_path(sid)):
        return send_file(backup_path(sid))
    abort(404)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
