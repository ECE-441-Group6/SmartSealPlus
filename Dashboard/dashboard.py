# Runs the web dashboard, likely using Flask. Gets stored/current data and sends it to the webpage.
#from flask import Flask, render_template

import csv
import hmac
import os
import re
import secrets
import sys
import time
from datetime import timedelta
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    send_from_directory,
    url_for,
)

REPOSITORY_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_PATH))

from Gateway.database import apply_retention_policy, get_latest_events, init_database
from Gateway.image_storage import IMAGE_FOLDER
from Dashboard.auth import verify_user

app = Flask(__name__)
SECRET_FILE = REPOSITORY_PATH / "Gateway" / ".dashboard_secret"


def _load_secret_key():
    configured = os.getenv("SMARTSEAL_DASHBOARD_SECRET")
    if configured:
        return configured

    try:
        return SECRET_FILE.read_bytes()
    except FileNotFoundError:
        key = secrets.token_bytes(32)
        try:
            with SECRET_FILE.open("xb") as secret_file:
                secret_file.write(key)
        except FileExistsError:
            key = SECRET_FILE.read_bytes()
        if os.name == "posix":
            SECRET_FILE.chmod(0o600)
        return key


app.config.update(
    SECRET_KEY=_load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SMARTSEAL_DASHBOARD_HTTPS") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)
init_database()
_last_retention_check = 0.0
ARCHIVE_DIRECTORY = REPOSITORY_PATH / "Gateway" / "archives"
ARCHIVE_FILENAME = re.compile(
    r"SmartSeal_Events_(?:"
    r"\d{2}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-[AP]M"
    r"|\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d+"
    r")\.csv"
)


def _archive_path(filename):
    if not ARCHIVE_FILENAME.fullmatch(filename):
        return None
    path = (ARCHIVE_DIRECTORY / filename).resolve()
    if path.parent != ARCHIVE_DIRECTORY.resolve() or not path.is_file():
        return None
    return path


def _csrf_token():
    token = session.get("csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": _csrf_token}


@app.before_request
def require_dashboard_account():
    global _last_retention_check
    now = time.monotonic()
    if now - _last_retention_check >= 3600:
        apply_retention_policy()
        _last_retention_check = now

    protected_endpoints = {"delete_archive", "logout"}
    if request.endpoint in protected_endpoints and not session.get("username"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Sign in to manage archives"}), 401
        return redirect(url_for("login"))

    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        expected = session.get("csrf_token", "")
        provided = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(expected, provided):
            abort(400, "Invalid CSRF token")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        authenticated_username = verify_user(username, password)
        if authenticated_username is None:
            error = "The username or password is incorrect."
        else:
            session.clear()
            session.permanent = True
            session["username"] = authenticated_username
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("home"))

    response = make_response(render_template("login.html", error=error))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    # Render the initial page with the latest events already loaded.
    events = get_latest_events()

    response = make_response(
        render_template("index.html", events=events)
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/api/events")
def events_api():
    # Provide the same event data as JSON for JavaScript refreshes.
    response = jsonify(get_latest_events())
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

#passes back list of valid archive file names
@app.route("/api/archives")
def archives_api():
    if not ARCHIVE_DIRECTORY.is_dir():
        return jsonify([])

    archives = sorted(
        (
            path.name
            for path in ARCHIVE_DIRECTORY.iterdir()
            if ARCHIVE_FILENAME.fullmatch(path.name) and path.is_file()
        ),
        reverse=True,
    )
    response = jsonify(archives)
    response.headers["Cache-Control"] = "no-store"
    return response

#passes csv headers to front end, assumes csv has these headers only (check csv header and info creation)
@app.route("/api/archives/<filename>")
def archive_events_api(filename):
    path = _archive_path(filename)
    if path is None:
        return jsonify({"error": "Archive not found"}), 404

    with path.open(newline="", encoding="utf-8") as archive_file:
        rows = []
        for event in csv.DictReader(archive_file):
            rows.append([
                int(event["id"]) if event.get("id") else None,
                event.get("timestamp"),
                int(event["seal_id"]) if event.get("seal_id") else None,
                int(event["event_sequence"]) if event.get("event_sequence") else None,
                float(event["temperature"]) if event.get("temperature") else None,
                int(event["tamper"]) if event.get("tamper") else 0,
                float(event["vibration"]) if event.get("vibration") else None,
                int(event["movement_type"]) if event.get("movement_type") else 0,
                event.get("image_path") or None,
                event.get("ai_analysis") or None,
            ])

    response = jsonify(rows)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/api/archives/<filename>", methods=["DELETE"])
def delete_archive(filename):
    path = _archive_path(filename)
    if path is None:
        return jsonify({"error": "Archive not found"}), 404

    try:
        path.unlink()
        # Preserve pictures still referenced by live events or other archives;
        # remove orphaned evidence as part of deleting the selected archive.
        from Gateway.database import _delete_unreferenced_images

        _delete_unreferenced_images()
    except OSError as error:
        return jsonify({"error": f"Could not delete archive: {error}"}), 500

    return jsonify({"deleted": filename})


#gets image file
@app.route("/images/<path:filename>")
def images(filename):
    # Serve captured or simulated evidence images from the gateway storage.
    return send_from_directory(IMAGE_FOLDER, filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", debug=False)
