import os
import hmac

from flask import Flask, Response, abort, request, send_from_directory

app = Flask(__name__)

SITE_ROOT = "/srv/site"
FLAG_PATH = "/home/burrow/flag.txt"

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


def submitted_token():
    # Accept the token either as a bearer header or a ?token= query param.
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer ") :]
    return request.args.get("token", "")


@app.route("/admin")
def admin():
    token = submitted_token()
    if ADMIN_TOKEN and hmac.compare_digest(token, ADMIN_TOKEN):
        with open(FLAG_PATH, "r", encoding="utf-8") as fh:
            flag = fh.read()
        return Response(
            f"Welcome, admin. Your flag:\n\n{flag}\n",
            mimetype="text/plain",
        )
    abort(401)


@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def site(path):
    # Send from directory to prevent normal path traversal / LFI
    return send_from_directory(SITE_ROOT, path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
