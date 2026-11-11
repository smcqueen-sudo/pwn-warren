import os

from flask import Flask, abort, request

app = Flask(__name__)

DOCS_DIR = "/app/docs"
DEFAULT_DOC = "welcome.txt"


@app.route("/")
def index():
    available = sorted(os.listdir(DOCS_DIR))
    links = "\n".join(
        f'<li><a href="/view?file={name}">{name}</a></li>' for name in available
    )
    return f"""
    <h1>Burrow Library</h1>
    <p>A humble collection of reading material. Pick a document:</p>
    <ul>{links}</ul>
    <p>Documents are served from <code>/view?file=&lt;name&gt;</code>.</p>
    """


@app.route("/view")
def view():
    requested = request.args.get("file", DEFAULT_DOC)
    path = os.path.join(DOCS_DIR, requested)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as document:
            contents = document.read()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        abort(404)

    return f"<h1>{requested}</h1><pre>{contents}</pre>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
