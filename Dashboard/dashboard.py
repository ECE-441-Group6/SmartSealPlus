# Runs the web dashboard, likely using Flask. Gets stored/current data and sends it to the webpage.
#from flask import Flask, render_template

#app = Flask(__name__)

#@app.route("/")
#def home():

 #   data = {
  #      "seal_id": 1,
   #     "temperature": 4.5,
    #    "tamper": False,
     #   "vibration": False
    #}

    #return render_template("index.html", data=data)

#if __name__ == "__main__":
 #   app.run(debug=True)


import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, send_from_directory

GATEWAY_PATH = Path(__file__).resolve().parents[1] / "Gateway"
sys.path.insert(0, str(GATEWAY_PATH))

from database import get_latest_events
from image_storage import IMAGE_FOLDER

app = Flask(__name__)


@app.route("/")
def home():
    # Render the initial page with the latest events already loaded.
    events = get_latest_events()

    return render_template(
        "index.html",
        events=events
    )


@app.route("/api/events")
def events_api():
    # Provide the same event data as JSON for JavaScript refreshes.
    return jsonify(get_latest_events())


@app.route("/images/<path:filename>")
def images(filename):
    # Serve captured or simulated evidence images from the gateway storage.
    return send_from_directory(IMAGE_FOLDER, filename)


if __name__ == "__main__":
    app.run(debug=True)