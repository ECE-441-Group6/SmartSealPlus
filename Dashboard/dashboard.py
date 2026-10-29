# Runs the web dashboard, likely using Flask. Gets stored/current data and sends it to the webpage.
#from flask import Flask, render_template

import csv
import re
import sys
from pathlib import Path

from flask import Flask, jsonify, make_response, render_template, send_from_directory

REPOSITORY_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_PATH))

from Gateway.database import get_latest_events
from Gateway.image_storage import IMAGE_FOLDER

app = Flask(__name__)
ARCHIVE_DIRECTORY = REPOSITORY_PATH / "Gateway" / "archives"
ARCHIVE_FILENAME = re.compile(r"gateway-events-\d{8}-\d{6}-\d{6}\.csv")


def _archive_path(filename):
    if not ARCHIVE_FILENAME.fullmatch(filename):
        return None
    path = (ARCHIVE_DIRECTORY / filename).resolve()
    if path.parent != ARCHIVE_DIRECTORY.resolve() or not path.is_file():
        return None
    return path


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
                event.get("image_path") or None,
                event.get("ai_analysis") or None,
            ])

    response = jsonify(rows)
    response.headers["Cache-Control"] = "no-store"
    return response

#gets image file
@app.route("/images/<path:filename>")
def images(filename):
    # Serve captured or simulated evidence images from the gateway storage.
    return send_from_directory(IMAGE_FOLDER, filename)


if __name__ == "__main__":
    app.run(debug=True)