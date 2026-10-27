# Runs the web dashboard, likely using Flask. Gets stored/current data and sends it to the webpage.
#from flask import Flask, render_template

import sys
from pathlib import Path

from flask import Flask, jsonify, make_response, render_template, send_from_directory

REPOSITORY_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_PATH))

from Gateway.database import get_latest_events
from Gateway.image_storage import IMAGE_FOLDER

app = Flask(__name__)


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


@app.route("/images/<path:filename>")
def images(filename):
    # Serve captured or simulated evidence images from the gateway storage.
    return send_from_directory(IMAGE_FOLDER, filename)


if __name__ == "__main__":
    app.run(debug=True)