"""Yurt/çamaşırhane topluluğu: arıza bildirme ve kayıp eşya panosu."""
import os
import secrets
import sqlite3

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

import db
import kurallar
import servis
from web import giris_gerekli

bp = Blueprint("yurt", __name__)


@bp.route("/makine/<int:machine_id>/ariza", methods=["GET", "POST"])
@giris_gerekli
def ariza_bildir(machine_id):
    """Öğrenci arıza bildirir (isteğe bağlı fotoğrafla). Görevli onaylayınca makine arızalı işaretlenir."""
    makine = db.makine_getir(machine_id)
    if makine is None or makine["laundry_room_id"] != servis.ogrenci_camasirhanesi(session["student_id"]):
        abort(404)
    if request.method == "GET":
        return render_template("ariza.html", makine=makine)

    aciklama = request.form.get("description", "").strip()
    hata = None
    if not 5 <= len(aciklama) <= 500:
        hata = "Sorunu 5-500 karakterle anlat (ör. \"Su boşaltmıyor\")."

    yukleme_klasoru = current_app.config["UPLOAD_DIR"]
    foto_yolu = None
    foto = request.files.get("photo")
    if hata is None and foto and foto.filename:
        veri = foto.read(kurallar.FOTO_SINIRI + 1)
        uzanti = kurallar.foto_uzantisi(veri)
        if len(veri) > kurallar.FOTO_SINIRI:
            hata = "Fotoğraf en fazla 5 MB olabilir."
        elif uzanti is None:
            hata = "Fotoğraf JPG, PNG ya da WEBP olmalı."
        else:
            os.makedirs(yukleme_klasoru, exist_ok=True)
            foto_yolu = f"{secrets.token_hex(16)}.{uzanti}"
            with open(os.path.join(yukleme_klasoru, foto_yolu), "wb") as f:
                f.write(veri)

    if hata is None:
        try:
            db.ariza_bildir(machine_id, session["student_id"], aciklama, foto_yolu)
        except sqlite3.IntegrityError:
            hata = "Bu makine için açık bir bildirimin zaten var. Görevli inceleyince yenisini yapabilirsin."
            if foto_yolu:  # kaydedilmeyen bildirimin fotoğrafı diskte kalmasın
                os.remove(os.path.join(yukleme_klasoru, foto_yolu))
    if hata:
        return render_template("ariza.html", makine=makine, hata=hata, aciklama=aciklama), 400

    flash("Arıza bildirimin yurt görevlisine iletildi. Görevli inceledikten sonra makinenin durumu güncellenecek.", "basarili")
    return redirect(url_for("randevu.makine"))


@bp.route("/kayip-esya", methods=["GET", "POST"])
@giris_gerekli
def kayip_esya():
    """Çamaşırhanenin kayıp eşya panosu: herkes kendi çamaşırhanesinin panosunu görür."""
    camasirhane = servis.ogrenci_camasirhanesi(session["student_id"])
    makineler = db.makineler(camasirhane)
    hata = None
    if request.method == "POST":
        aciklama = request.form.get("description", "").strip()
        machine_id = request.form.get("machine_id", type=int)
        if machine_id is not None and machine_id not in {m["machine_id"] for m in makineler}:
            machine_id = None  # başka çamaşırhanenin makinesi seçilemez
        if not 3 <= len(aciklama) <= 200:
            hata = "Eşyayı 3-200 karakterle anlat (ör. \"Mavi çizgili çorap\")."
        else:
            db.kayip_esya_ekle(camasirhane, session["student_id"], machine_id, aciklama)
            flash("İlanın panoya eklendi.", "basarili")
            return redirect(url_for("yurt.kayip_esya"))
    return render_template("kayip_esya.html", esyalar=db.kayip_esyalar(camasirhane), makineler=makineler, hata=hata,
                           camasirhane_adi=servis.camasirhane_adi(camasirhane)), (400 if hata else 200)


@bp.route("/kayip-esya/<int:item_id>/kapat", methods=["POST"])
@giris_gerekli
def kayip_esya_kapat(item_id):
    if db.kayip_esya_kapat(item_id, session["student_id"]):
        flash("İlan kapatıldı ve panodan kaldırıldı.", "basarili")
    else:
        flash("Bu ilanı yalnızca ilanı veren kapatabilir.", "hata")
    return redirect(url_for("yurt.kayip_esya"))
