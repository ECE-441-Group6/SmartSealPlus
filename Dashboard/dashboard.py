# Runs the web dashboard, likely using Flask. Gets stored/current data and sends it to the webpage.
#from flask import Flask, render_template

import csv
from collections import defaultdict, deque
import hmac
import os
import re
import secrets
import stat
import sys
import time
from datetime import timedelta
from pathlib import Path
from threading import Lock

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
from waitress import serve

REPOSITORY_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_PATH))

from Gateway.database import (
    ARCHIVE_DIRECTORY,
    apply_retention_policy,
    get_latest_events,
    init_database,
)
from Gateway.image_storage import IMAGE_FOLDER
from Dashboard.auth import verify_user

app = Flask(__name__)
SECRET_FILE = REPOSITORY_PATH / "Gateway" / ".dashboard_secret"


def _load_secret_key():
    configured = os.getenv("SMARTSEAL_DASHBOARD_SECRET")
    if configured:
        key = configured.encode("utf-8")
        if len(key) < 32:
            raise RuntimeError("SMARTSEAL_DASHBOARD_SECRET must be at least 32 bytes.")
        return key

    if SECRET_FILE.is_symlink():
        raise RuntimeError(f"{SECRET_FILE} must not be a symbolic link.")

    def read_created_secret():
        # Another dashboard process may have won the exclusive create race and
        # still be writing the 32-byte key. Wait briefly instead of accepting
        # a partial secret or failing spuriously during concurrent startup.
        key = b""
        for _ in range(50):
            try:
                key = SECRET_FILE.read_bytes()
            except FileNotFoundError:
                key = b""
            if len(key) >= 32:
                return key
            time.sleep(0.02)
        return key

    try:
        if os.name == "posix" and SECRET_FILE.exists():
            # Restrict an existing key before reading it, rather than leaving
            # a permissive mode in place during dashboard startup.
            SECRET_FILE.chmod(0o600)
        key = SECRET_FILE.read_bytes()
    except FileNotFoundError:
        key = secrets.token_bytes(32)
        try:
            descriptor = os.open(
                SECRET_FILE,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            key = read_created_secret()
        else:
            with os.fdopen(descriptor, "wb") as secret_file:
                secret_file.write(key)
                secret_file.flush()
                os.fsync(secret_file.fileno())

    if len(key) < 32:
        raise RuntimeError(
            f"{SECRET_FILE} must contain at least 32 random bytes."
        )
    if os.name == "posix":
        mode = stat.S_IMODE(SECRET_FILE.stat().st_mode)
        if mode & 0o077:
            SECRET_FILE.chmod(0o600)
    return key


app.config.update(
    SECRET_KEY=_load_secret_key(),
    # This dashboard has no upload endpoints; reject oversized form bodies.
    MAX_CONTENT_LENGTH=16 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SMARTSEAL_DASHBOARD_HTTPS") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)
init_database()
_last_retention_check = 0.0
ARCHIVE_FILENAME = re.compile(
    r"SmartSeal_Events_(?:"
    r"\d{2}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-[AP]M"
    r"|\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d+"
    r")\.csv"
)
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 8
MAX_TRACKED_LOGIN_CLIENTS = 4096
_login_failures = defaultdict(deque)
_login_failures_lock = Lock()


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; object-src 'none'; "
        "frame-ancestors 'none'; form-action 'self'; connect-src 'self'; "
        "img-src 'self' data: https://unpkg.com https://*.tile.openstreetmap.org; "
        "script-src 'self' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com",
    )
    if app.config["SESSION_COOKIE_SECURE"]:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000"
        )
    return response


def _login_retry_after(client):
    now = time.monotonic()
    with _login_failures_lock:
        attempts = _login_failures.get(client)
        if not attempts:
            return 0
        while attempts and now - attempts[0] >= LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if not attempts:
            _login_failures.pop(client, None)
            return 0
        if len(attempts) < LOGIN_MAX_FAILURES:
            return 0
        return max(1, int(LOGIN_WINDOW_SECONDS - (now - attempts[0])))


def _record_login_failure(client):
    now = time.monotonic()
    with _login_failures_lock:
        attempts = _login_failures[client]
        while attempts and now - attempts[0] >= LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        attempts.append(now)

        if len(_login_failures) > 1024:
            for stale_client, stale_attempts in list(_login_failures.items()):
                while (
                    stale_attempts
                    and now - stale_attempts[0] >= LOGIN_WINDOW_SECONDS
                ):
                    stale_attempts.popleft()
                if not stale_attempts:
                    _login_failures.pop(stale_client, None)

        # Keep attacker-controlled remote addresses from growing this
        # in-memory throttle table without bound.
        while len(_login_failures) > MAX_TRACKED_LOGIN_CLIENTS:
            oldest_client = min(
                _login_failures,
                key=lambda address: _login_failures[address][0],
            )
            _login_failures.pop(oldest_client, None)


def _clear_login_failures(client):
    with _login_failures_lock:
        _login_failures.pop(client, None)


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
    status_code = 200
    if request.method == "POST":
        client = request.remote_addr or "unknown"
        retry_after = _login_retry_after(client)
        if retry_after:
            error = f"Too many failed attempts. Try again in {retry_after} seconds."
            status_code = 429
        else:
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            authenticated_username = verify_user(username, password)
            if authenticated_username is None:
                _record_login_failure(client)
                error = "The username or password is incorrect."
            else:
                _clear_login_failures(client)
                session.clear()
                session.permanent = True
                session["username"] = authenticated_username
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("home"))

    response = make_response(render_template("login.html", error=error))
    response.headers["Cache-Control"] = "no-store"
    response.status_code = status_code
    if status_code == 429:
        response.headers["Retry-After"] = str(retry_after)
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
        response = jsonify([])
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        return response

    archives = sorted(
        (
            path.name
            for path in ARCHIVE_DIRECTORY.iterdir()
            if ARCHIVE_FILENAME.fullmatch(path.name) and path.is_file()
        ),
        reverse=True,
    )
    response = jsonify(archives)
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
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
                float(event["gps_latitude"])
                if event.get("gps_latitude") not in (None, "") else None,
                float(event["gps_longitude"])
                if event.get("gps_longitude") not in (None, "") else None,
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
    except OSError:
        app.logger.exception("Could not delete archive %s", filename)
        return jsonify({"error": "Could not delete the selected archive."}), 500

    return jsonify({"deleted": filename})


#gets image file
@app.route("/images/<path:filename>")
def images(filename):
    # Serve captured or simulated evidence images from the gateway storage.
    response = send_from_directory(IMAGE_FOLDER, filename)
    response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    # Use a production WSGI server for LAN access instead of Flask's
    # development server. Bound resources to limit the effect of slow or
    # oversized client requests on the Pi.
    serve(
        app,
        host=os.getenv(
            "SMARTSEAL_DASHBOARD_HOST",
            "0.0.0.0" if os.name == "posix" else "127.0.0.1",
        ),
        port=int(os.getenv("SMARTSEAL_DASHBOARD_PORT", "5000")),
        threads=4,
        connection_limit=64,
        channel_timeout=30,
        max_request_header_size=8192,
        max_request_body_size=16 * 1024,
        clear_untrusted_proxy_headers=True,
    )
