from flask import Flask, render_template, request, redirect, url_for 
from flask import session, flash
from datetime import datetime, timedelta
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

    # Saat seçiciden gelen gün + saat, tam saatlik bir başlangıç zamanına çevrilir
    gun = request.args.get("gun")
    saat = request.args.get("saat")
    if gun and saat and saat.isdigit():
        zaman = f"{gun} {int(saat):02d}:00:00"

    # Seçim yoksa bir sonraki tam saat gösterilir (randevular tam saatte başlar)
    if zaman is None:
        sonraki_saat = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        zaman = sonraki_saat.strftime("%Y-%m-%d %H:%M:%S")

    makineler = db.makine_durumlari(zaman)
    return render_template("makineler.html", makineler=makineler, zaman=zaman)

@app.route("/randevu", methods=["POST"])
def randevu_al():
    # Giriş yapmamışsa giriş sayfasına
    if not session.get("student_id"):
        return redirect(url_for("giris"))
    student_id = session["student_id"]

    # Formdan gelen bilgiler
    machine_id = request.form.get("machine_id", type=int)
    start_time = request.form.get("start_time", "")
    program = request.form.get("program")

    # Hata olursa mesajla aynı saatin sayfasına dön
    def hata(mesaj):
        flash(mesaj, "hata")
        return redirect(url_for("makine", zaman=start_time))

    makine = db.makine_getir(machine_id)
    if makine is None:
        return hata("Makine bulunamadı.")

    try:
        baslangic = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return hata("Geçersiz saat.")
    sure = 2 if makine["machine_type"] == "dryer" else 1
    bitis = baslangic + timedelta(hours=sure)

    # ---- KURALLAR (her biri: if ...: return hata("...")) ----

    # a) Geçmiş bir saat olamaz
    if baslangic < datetime.now():
        return hata("Geçmiş bir saate randevu alınamaz.")

    # b) Çalışma saatleri içinde olmalı
    #    Hafta içi 08:00-20:00, hafta sonu 09:00-17:00. Randevu kapanıştan önce bitmeli.
    hafta_sonu = baslangic.weekday() >= 5          # 5 = cumartesi, 6 = pazar
    acilis = 9 if hafta_sonu else 8
    kapanis = 17 if hafta_sonu else 20
    if baslangic.hour < acilis or bitis > baslangic.replace(hour=kapanis):
        return hata(f"Çamaşırhane bu gün {acilis:02d}:00-{kapanis:02d}:00 arası açık.")

    # c) Makine arızalı olamaz
    if makine["out_of_order"]:
        return hata("Bu makine arızalı.")

    # d) Program: çamaşırda zorunlu, kurutmada yok
    if makine["machine_type"] == "dryer":
        program = None
    else:
        if program not in ("colored", "white"):
            return hata("Çamaşır makinesi için bir program seçmelisin.")
        
        # e) Haftalık çamaşır hakkı (en fazla 2)
        kontrol = db.haftalik_camasir_sayisi(student_id, start_time)
        if kontrol >= 2 :
            return hata("Bu hafta 2 çamaşır hakkını kullandın.")
    
    # f) Makine bu aralıkta müsait olmalı
    bas = baslangic.strftime("%Y-%m-%d %H:%M:%S")
    bit = bitis.strftime("%Y-%m-%d %H:%M:%S")
    if not db.makine_musait_mi(machine_id, bas, bit):
        return hata("Bu makine o saatte dolu.")
    
    # g) Öğrencinin bu aralıkta başka randevusu olmamalı
    ogrenci = db.ogrenci_musait_mi(student_id, bas ,bit)
    if not ogrenci:
        return hata("Bu saatte zaten başka bir randevun var.")
    # ---------------------------------------------------------

    try:
        db.randevu_ekle(student_id, machine_id, start_time, program)
    except sqlite3.IntegrityError:
        return hata("Bu makine o saatte az önce doldu.")

    flash("Randevun alındı.", "basarili")
    return redirect(url_for("makine", zaman=start_time))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
