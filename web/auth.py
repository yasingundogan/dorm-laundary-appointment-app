"""Giriş, çıkış, kayıt."""
import sqlite3
from datetime import timedelta

from flask import Blueprint, redirect, render_template, request, session, url_for

import db
import kurallar
import servis
import zaman

bp = Blueprint("auth", __name__)

GIRIS_DENEME_SINIRI = 5
GIRIS_KILIT_SURESI = timedelta(minutes=15)
# shortcut: hatalı giriş sayacı bellekte ve tek süreçte tutulur; birden çok sunucu sürecine geçilirse veritabanına/Redis'e taşınmalı
_hatali_girisler = {}  # e-posta -> son hatalı deneme zamanları


@bp.route("/")
def ana_sayfa():
    return redirect(url_for("auth.giris"))


@bp.route("/giris", methods=["GET", "POST"])
def giris():
    if request.method == "GET":
        return render_template("giris.html")

    form = request.form
    email = form.get("email", "").strip().lower()

    # Kaba kuvvet denemelerine karşı: aynı e-postaya 15 dakikada en fazla 5 hatalı deneme
    simdi = zaman.simdi()
    denemeler = [t for t in _hatali_girisler.get(email, []) if simdi - t < GIRIS_KILIT_SURESI]
    if len(denemeler) >= GIRIS_DENEME_SINIRI:
        dakika = int((denemeler[0] + GIRIS_KILIT_SURESI - simdi).total_seconds() // 60) + 1
        hata = f"Çok fazla hatalı deneme. {dakika} dakika sonra tekrar deneyin."
        return render_template("giris.html", hata=hata, form=form), 429

    ogrenci = db.ogrenci_dogrula(email, form.get("password", ""))
    if ogrenci is None:
        _hatali_girisler[email] = denemeler + [simdi]
        return render_template("giris.html", hata="Giriş bilgileri hatalı.", form=form)

    _hatali_girisler.pop(email, None)
    session.clear()
    session["student_id"] = ogrenci["student_id"]
    session["student_name"] = ogrenci["student_name"]
    return redirect(url_for("randevu.makine"))


@bp.route("/cikis", methods=["POST"])  # GET değil: başka bir site bağlantıyla oturumu kapatamasın
def cikis():
    session.clear()
    return redirect(url_for("auth.giris"))


@bp.route("/kayit", methods=["GET", "POST"])
def kayit():
    def sayfa(hata=None):
        return render_template("kayit.html", hata=hata, form=request.form, camasirhaneler=db.camasirhaneler())

    if request.method == "GET":
        return sayfa()

    form = request.form
    sifre = form.get("password", "")
    # Boşluklar atılır; e-posta küçük harfe çevrilir: Ali@ ile ali@ aynı hesap
    alanlar, hata = kurallar.ogrenci_alanlarini_dogrula(form, ["first_name", "last_name", "phone", "email", "room"])
    camasirhane = servis.camasirhane_sec(form)
    if hata is None and camasirhane is None:
        hata = "Yurdunu ve bloğunu seç."
    if hata is None and sifre != form.get("confirm_password"):
        hata = "Şifreler eşleşmiyor."
    if hata is None and len(sifre) < 8:
        hata = "Şifre 8 karakterden az olamaz."
    if hata:
        return sayfa(hata)

    try:
        db.ogrenci_ekle(alanlar["first_name"], alanlar["last_name"], alanlar["phone"], alanlar["email"],
                        alanlar["room"], sifre, camasirhane)
    except sqlite3.IntegrityError:
        return sayfa("Bu e-posta veya telefon numarası zaten kayıtlı ")
    return redirect(url_for("auth.giris"))
