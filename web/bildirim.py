"""Uygulama içi bildirimler."""
from flask import Blueprint, render_template, session

import db
from web import giris_gerekli

bp = Blueprint("bildirim", __name__)


@bp.route("/bildirimler")
@giris_gerekli
def bildirimler():
    liste = db.bildirimler(session["student_id"])
    db.bildirimleri_okundu_yap(session["student_id"])  # liste okunmadan önce alındı: yeni olanlar vurgulu görünür
    return render_template("bildirimler.html", bildirimler=liste, okunmamis_bildirim=0)
