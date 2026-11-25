"""Profil: bilgiler, randevularım, bilgileri düzenleme."""
import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

import db
import kurallar
import servis
import zaman
from web import durum_penceresi, giris_gerekli

bp = Blueprint("profil", __name__)


@bp.route("/profil")
@giris_gerekli
def profil():
    db.gecmis_randevulari_tamamla()
    simdi = zaman.simdi_metin()
    randevular = db.ogrenci_randevulari(session["student_id"])
    # Aktif ve henüz bitmemiş olanlar yaklaşan, geri kalan her şey geçmiş
    yaklasan = [r for r in randevular if r["status"] == "active" and r["end_time"] > simdi][::-1]
    gecmis = [r for r in randevular if r not in yaklasan]
    return render_template("profil.html", ogrenci=db.ogrenci_getir(session["student_id"]), yaklasan=yaklasan,
                           gecmis=gecmis, hak=servis.haftalik_hak(session["student_id"], simdi), simdi=simdi,
                           yikama=durum_penceresi())


@bp.route("/profil/duzenle", methods=["GET", "POST"])
@giris_gerekli
def profil_duzenle():
    ogrenci = db.ogrenci_getir(session["student_id"])

    def sayfa(hata=None, form=None):
        return render_template("profil_duzenle.html", ogrenci=ogrenci, form=form, hata=hata,
                               camasirhaneler=db.camasirhaneler())

    if request.method == "GET":
        return sayfa()

    alanlar, hata = kurallar.ogrenci_alanlarini_dogrula(request.form, ["first_name", "last_name", "phone", "room"])
    camasirhane = servis.camasirhane_sec(request.form) if "laundry_room_id" in request.form else ogrenci["laundry_room_id"]
    if hata is None and camasirhane is None:
        hata = "Geçerli bir yurt ve blok seç."
    if hata is None:
        try:
            db.ogrenci_guncelle(session["student_id"], alanlar["first_name"], alanlar["last_name"],
                                alanlar["phone"], alanlar["room"], camasirhane)
        except sqlite3.IntegrityError:
            hata = "Bu telefon numarası başka bir hesapta kayıtlı."
    if hata:
        return sayfa(hata, request.form)

    session["student_name"] = alanlar["first_name"]  # üst çubuktaki ad güncellensin
    flash("Bilgilerin güncellendi.", "basarili")
    return redirect(url_for("profil.profil"))
