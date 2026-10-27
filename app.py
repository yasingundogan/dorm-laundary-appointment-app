from flask import Flask, render_template
import db

app = Flask(__name__)


@app.route("/")
def ana_sayfa():
    return "Merhaba çamaşırhane!"


@app.route("/makineler")
def makine():
    makineler = db.tum_makineler()
    return render_template("makineler.html", makineler=makineler)


if __name__ == "__main__":
    app.run(debug=True, port=5001)