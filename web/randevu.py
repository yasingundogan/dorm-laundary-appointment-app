"""Makineler sayfası, randevu alma/iptal, bekleme listesi."""
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

import db
import kurallar
import servis
import zaman
from web import durum_penceresi, giris_gerekli

bp = Blueprint("randevu", __name__)

GUN_ADLARI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
AY_ADLARI = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def _secim():
    """?gun=&saat= (gün şeridi / saat seçici) ya da ?zaman= (randevu sonrası yönlendirme); geçersizse None."""
    try:
        if request.args.get("gun"):
            return datetime.strptime(request.args["gun"], "%Y-%m-%d").replace(hour=int(request.args.get("saat") or 0))
        if request.args.get("zaman"):
            return zaman.oku(request.args["zaman"])
    except ValueError:
        pass
    return None


@bp.route("/makineler")
def makine():
    db.gecmis_randevulari_tamamla()
    simdi = zaman.simdi()
    gunler = kurallar.secilebilir_gunler(simdi)

    # Geçmiş, kapalı ya da gösterilmeyen bir gün seçildiyse ilk açık güne geçilir;
    # saat o gün yoksa (geçmiş / kapalı) o günün ilk açık saati seçilir
    secim = _secim()
    secili_gun = next((g for g in gunler if secim and g.date() == secim.date()), gunler[0])
    saatler = kurallar.baslangic_saatleri(secili_gun, simdi)
    saat = secim.hour if secim and secim.hour in saatler else saatler[0]
    secili_an = f"{secili_gun:%Y-%m-%d} {saat:02d}:00:00"

    # Öğrenci kendi çamaşırhanesini görür; giriş yapmamış ziyaretçi listeden seçer
    camasirhaneler = db.camasirhaneler()
    student_id = session.get("student_id")
    if student_id:
        camasirhane = servis.ogrenci_camasirhanesi(student_id)
    else:
        istenen = request.args.get("camasirhane", type=int)
        gecerli = {r["laundry_room_id"] for r in camasirhaneler}
        camasirhane = istenen if istenen in gecerli else camasirhaneler[0]["laundry_room_id"]

    makineler = db.makine_durumlari(secili_an, camasirhane)
    serit = servis.gun_seridi(makineler, camasirhane, secili_gun, simdi, student_id)
    simdiki = {mid: dict(hucreler)[saat] for mid, hucreler in serit.items()}  # seçili saatteki durum (kart ve çizim)
    beyaz_olur = {mid: kurallar.beyaz_sigan_saatler(hucreler) for mid, hucreler in serit.items()}

    yikama = durum_penceresi()  # altta çalışan / az önce biten çamaşır
    return render_template(
        "makineler.html", makineler=makineler, zaman=secili_an, sureler=kurallar.SURELER,
        hak=servis.haftalik_hak(student_id, secili_an) if student_id else None,
        sirada=db.siradaki_makineler(student_id, secili_an) if student_id else set(),
        camasirhaneler=camasirhaneler, camasirhane=camasirhane, camasirhane_adi=servis.camasirhane_adi(camasirhane),
        serit=serit, simdiki=simdiki, beyaz_olur=beyaz_olur, arizalar=db.acik_ariza_sayilari(camasirhane),
        gunler=gunler, secili_gun=secili_gun, saatler=saatler, saat=saat, bugun=simdi.date(),
        gun_adlari=GUN_ADLARI, ay_adlari=AY_ADLARI, yikama=yikama,
    )


@bp.route("/randevu", methods=["POST"])
@giris_gerekli
def randevu_al():
    start_time = request.form.get("start_time", "")
    bitis, hata = servis.randevu_olustur(session["student_id"], request.form.get("machine_id", type=int),
                                         start_time, request.form.get("program"))
    if hata:
        flash(hata, "hata")
        return redirect(url_for("randevu.makine", zaman=start_time))

    flash("Randevun alındı.", "basarili")
    makine = db.makine_getir(request.form.get("machine_id", type=int))
    if makine["machine_type"] == "washer" and kurallar.kurutma_onerisi_olur_mu(bitis, zaman.simdi()):
        flash({
            "saat": f"{bitis:%H:%M}",
            "url": url_for("randevu.makine", gun=f"{bitis:%Y-%m-%d}", saat=bitis.hour, _anchor="kurutma"),
        }, "oneri")
    return redirect(url_for("randevu.makine", zaman=start_time))


@bp.route("/randevu/<int:appointment_id>/iptal", methods=["POST"])
@giris_gerekli
def randevu_iptal(appointment_id):
    sonuc = servis.randevu_iptal_et(appointment_id, session["student_id"])
    if sonuc == "yok":
        abort(404)  # başkasının randevusu "yok" gibi davranır: id tahmin edilerek bilgi sızdırılmasın
    if sonuc == "olmaz":
        flash("Yalnızca henüz başlamamış randevular iptal edilebilir.", "hata")
    else:
        flash("Randevun iptal edildi.", "basarili")
    return redirect(url_for("profil.profil"))


@bp.route("/sira", methods=["POST"])
@giris_gerekli
def sira():
    """Dolu bir makine + saat için bekleme listesine gir / çık."""
    machine_id = request.form.get("machine_id", type=int)
    start_time = request.form.get("start_time", "")
    try:
        baslangic = zaman.oku(start_time)
    except ValueError:
        abort(400)
    hata = servis.sira_hatasi(session["student_id"], machine_id, baslangic)
    if hata:
        flash(hata, "hata")
    elif request.form.get("islem") == "cik":
        db.siradan_cik(session["student_id"], machine_id, start_time)
        flash("Sıradan çıktın.", "basarili")
    else:
        db.siraya_gir(session["student_id"], machine_id, start_time)
        flash("Sıraya girdin. Bu saat boşalırsa bildirim alacaksın.", "basarili")
    return redirect(url_for("randevu.makine", zaman=start_time))
