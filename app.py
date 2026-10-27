from flask import Flask, render_template, request
from datetime import datetime
import db



app = Flask(__name__)


@app.route("/")
def ana_sayfa():
    return "Merhaba çamaşırhane!"


@app.route("/makineler")
def makine():
    zaman = request.args.get("zaman")
    if zaman is None:
        zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    makineler = db.makine_durumlari(zaman)   
    return render_template("makineler.html", makineler=makineler , zaman=zaman)

if __name__ == "__main__":
    app.run(debug=True, port=5001)