from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import db

app = Flask(__name__)


@app.route("/")
def ana_sayfa():
    return redirect(url_for("giris"))


@app.route("/giris", methods=["GET", "POST"])
def giris():
    # Şablon arayüzüdür; gerçek kimlik doğrulaması henüz eklenmemiştir.
    return render_template("giris.html")


@app.route("/kayit", methods=["GET", "POST"])
def kayit():
    # Şablon arayüzüdür; gerçek kayıt/veritabanı işlemi henüz eklenmemiştir.
    return render_template("kayit.html")


@app.route("/makineler")
def makine():
    zaman = request.args.get("zaman")
    if zaman is None:
        zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    makineler = db.makine_durumlari(zaman)
    return render_template("makineler.html", makineler=makineler, zaman=zaman)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
