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


from flask import Flask, render_template
from database import get_latest_events

app = Flask(__name__)


@app.route("/")
def home():

    events = get_latest_events()

    return render_template(
        "index.html",
        events=events
    )


if __name__ == "__main__":
    app.run(debug=True)