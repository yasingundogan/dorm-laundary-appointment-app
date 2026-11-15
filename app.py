from flask import Flask, render_template, request, redirect, url_for 
from flask import session
from datetime import datetime
import db
import sqlite3
import os
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


@app.route("/")
def ana_sayfa():
    return redirect(url_for("giris"))


@app.route("/giris", methods=["GET", "POST"])
def giris():
    if request.method == "GET":
        return render_template("giris.html")

    form = request.form
    ogrenci = db.ogrenci_dogrula(form.get("email"), form.get("password"))

    if ogrenci is None:
        return render_template("giris.html", hata="Giriş bilgileri hatalı.", form=form)

    session.clear()
    session["student_id"] = ogrenci["student_id"]
    session["student_name"] = ogrenci["student_name"]
    return redirect(url_for("makine"))

@app.route("/cikis", methods=["GET", "POST"])
def cikis():
    session.clear()
    return redirect(url_for("giris"))


@app.route("/kayit", methods=["GET", "POST"])
def kayit():
    if request.method == "GET":
        return render_template("kayit.html")

    form = request.form
    sifre = form.get("password", "")
    sifre_tekrar = form.get("confirm_password")
    kontrol = ["first_name" , "last_name" , "phone" , "email" , "room" ]

    # 1. Sunucu tarafı kontroller
    for i in kontrol:
        if not form.get(i ,"").strip():
            return render_template("kayit.html" , hata="Boş alan bırakılamaz." , form=form)
    
    if sifre != sifre_tekrar :
        return render_template("kayit.html", hata="Şifreler eşleşmiyor.", form=form)
    if len(sifre) < 8:
        return render_template("kayit.html", hata="Şifre 8 karakterden az olamaz.", form=form)

    # 2. Kaydetmeyi dene
    try:
        db.ogrenci_ekle(
            form.get("first_name"),
            form.get("last_name"),        # soyad
            form.get("phone"),        # telefon
            form.get("email"),        # email
            form.get("room"),        # oda
            sifre,
        )
    except sqlite3.IntegrityError:
        return render_template("kayit.html", hata="Bu e-posta veya telefon numarası zaten kayıtlı ", form=form)

    # 3. Başarılı: giriş sayfasına yönlendir
    return redirect(url_for("giris"))

@app.route("/makineler")
def makine():
    zaman = request.args.get("zaman")
    if zaman is None:
        zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    makineler = db.makine_durumlari(zaman)
    return render_template("makineler.html", makineler=makineler, zaman=zaman)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
