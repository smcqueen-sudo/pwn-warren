import os
import subprocess

from flask import Flask, abort, redirect, request, send_file

app = Flask(__name__)

UPLOAD_DIR = "/app/uploads"
BACKUP_PATH = "/app/backups/backup.tgz"


@app.route("/")
def index():
    uploads = sorted(os.listdir(UPLOAD_DIR))
    items = "\n".join(f"<li>{name}</li>" for name in uploads)

    download_link = ""
    if os.path.exists(BACKUP_PATH):
        download_link = '<p><a href="/download">Download latest backup</a></p>'

    return f"""
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


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files["f"]
    # For those curious, a potential fix to this exploit could be doing:
    # `secure_filename(f.filename)` here instead :D
    name = os.path.basename(f.filename)
    f.save(os.path.join(UPLOAD_DIR, name))
    return redirect("/")


@app.route("/backup", methods=["POST"])
def backup():
    subprocess.run("tar czf /app/backups/backup.tgz *", shell=True, cwd=UPLOAD_DIR)
    return redirect("/")


@app.route("/download")
def download():
    if os.path.exists(BACKUP_PATH):
        return send_file(BACKUP_PATH)
    else:
        abort(404)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
