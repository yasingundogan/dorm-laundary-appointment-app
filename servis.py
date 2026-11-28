"""İş akışları: kuralları (kurallar.py) veritabanıyla (db.py) birleştirir.

Web sayfaları (web/) yalnızca formu okur, buradaki fonksiyonları çağırır ve sonucu gösterir.
Görevli paneli ya da ileride bir API de aynı fonksiyonları kullanır.
"""
import sqlite3
from datetime import datetime, timedelta

import db
import kurallar
import zaman


# ---- Öğrenci / çamaşırhane ----

def ogrenci_camasirhanesi(student_id):
    """Öğrencinin çamaşırhanesi (id). Oturumda tutulmaz: profilden değişebilir."""
    return db.ogrenci_getir(student_id)["laundry_room_id"]


def camasirhane_sec(form):
    """Formdan gelen çamaşırhane id'si; tek çamaşırhane varsa seçim gerekmez. Geçersizse None."""
    odalar = {r["laundry_room_id"] for r in db.camasirhaneler()}
    secim = form.get("laundry_room_id", type=int)
    if secim is None and len(odalar) == 1:
        return next(iter(odalar))
    return secim if secim in odalar else None


def camasirhane_adi(laundry_room_id):
    return next(f"{r['dorm_name']} · {r['block_name']}" for r in db.camasirhaneler()
                if r["laundry_room_id"] == laundry_room_id)


def haftalik_hak(student_id, gun_metni):
    """gun_metni'nin (YYYY-MM-DD...) içinde olduğu haftanın kalan çamaşır hakkı; geçersiz tarihte None."""
    try:
        gun = datetime.strptime(gun_metni[:10], "%Y-%m-%d")
    except ValueError:
        return None
    pazartesi, pazar = kurallar.hafta_araligi(gun)
    kullanilan = db.haftalik_camasir_sayisi(student_id, gun_metni[:10])
    return {
        "kalan": max(kurallar.HAFTALIK_CAMASIR_HAKKI - kullanilan, 0),
        "toplam": kurallar.HAFTALIK_CAMASIR_HAKKI,
        "aralik": f"{pazartesi:%d.%m} – {pazar:%d.%m}",
    }


def gun_seridi(makineler, laundry_room_id, gun, simdi, student_id):
    """O günün zaman şeridi (bkz. kurallar.serit_hesapla)."""
    randevular = [(r["machine_id"], zaman.oku(r["start_time"]), zaman.oku(r["end_time"]), r["student_id"])
                  for r in db.gun_dolulugu(laundry_room_id, f"{gun:%Y-%m-%d}")]
    return kurallar.serit_hesapla(makineler, randevular, gun, simdi, student_id)


# ---- Randevu ----

def randevu_olustur(student_id, machine_id, start_time, program):
    """Randevu alır. (bitis, None) ya da (None, hata mesajı) döner.
    Haftalık hak ve çakışma kontrolleri kayıtla aynı kilitli işlemde yapılır: aynı anda gelen iki istek
    ikisi birden "müsait" görüp çakışan (ör. 14:00 ve 15:00 kurutma) randevu yazamaz."""
    makine = db.makine_getir(machine_id)
    try:
        baslangic = zaman.oku(start_time)
    except ValueError:
        return None, "Geçersiz saat."
    simdi = zaman.simdi()
    hata = kurallar.randevu_hatasi(makine, ogrenci_camasirhanesi(student_id), baslangic, program, simdi)
    if hata:
        return None, hata

    if makine["machine_type"] == "dryer":
        program = None  # kurutmada program yok
    bitis = kurallar.bitis_saati(baslangic, makine["machine_type"], program)
    bas, bit = zaman.metin(baslangic), zaman.metin(bitis)
    try:
        with db.islem() as conn:
            if makine["machine_type"] == "washer" and \
                    db.haftalik_camasir_sayisi(student_id, bas, conn) >= kurallar.HAFTALIK_CAMASIR_HAKKI:
                return None, f"Bu hafta {kurallar.HAFTALIK_CAMASIR_HAKKI} çamaşır hakkını kullandın."
            if not db.makine_musait_mi(machine_id, bas, bit, conn):
                return None, "Bu makine o saatte dolu."
            if not db.ogrenci_musait_mi(student_id, bas, bit, conn):
                return None, "Bu saatte zaten başka bir randevun var."
            db.randevu_ekle(student_id, machine_id, bas, bit, program, conn)
    except sqlite3.IntegrityError:
        return None, "Bu makine o saatte az önce doldu."
    return bitis, None


def randevu_iptal_et(appointment_id, student_id):
    """None: iptal edildi. "yok": randevu yok ya da başkasının. "olmaz": başlamış/aktif değil.
    İptal edilen saati bekleyenlere aynı işlemde bildirim gider."""
    with db.islem() as conn:
        randevu = db.randevu_getir(appointment_id, conn)
        if randevu is None or randevu["student_id"] != student_id:
            return "yok"
        if not kurallar.iptal_edilebilir_mi(randevu, zaman.simdi()):
            return "olmaz"
        db.randevu_iptal(appointment_id, conn)
        db.sirayi_bilgilendir(appointment_id, conn)
    return None


def _yikama(randevu_id, machine_type, machine_no, program, baslangic, bitis, simdi, demo=False):
    tur = "Kurutma" if machine_type == "dryer" else "Çamaşır"
    return {
        "id": randevu_id, "tur": machine_type, "makine": f"{tur} makinesi {machine_no}",
        "program": {"colored": "Renkli", "white": "Beyaz"}.get(program),
        "baslangic": f"{baslangic:%H:%M}", "bitis": f"{bitis:%H:%M}", "demo": demo,
        **kurallar.yikama_durumu(baslangic, bitis, simdi),
    }


def calisan_yikama(student_id):
    """Ana ekrandaki durum penceresi için öğrencinin çalışan (ya da son 30 dakikada biten) çamaşırı; yoksa None."""
    simdi = zaman.simdi()
    r = db.calisan_randevu(student_id, zaman.metin(simdi), zaman.metin(simdi - kurallar.HAZIR_GOSTERIM_SURESI))
    if r is None:
        return None
    return _yikama(r["appointment_id"], r["machine_type"], r["machine_no"], r["program"],
                   zaman.oku(r["start_time"]), zaman.oku(r["end_time"]), simdi)


def demo_yikama(student_id, machine_type, kalan_sn):
    """Test için: öğrencinin çamaşırhanesindeki ilk makinede, kalan_sn saniye sonra bitecek sahte bir çamaşır.
    Veritabanına bir şey yazılmaz."""
    makine = next((m for m in db.makineler(ogrenci_camasirhanesi(student_id)) if m["machine_type"] == machine_type), None)
    if makine is None:
        return None
    program = None if machine_type == "dryer" else "colored"
    simdi = zaman.simdi()
    bitis = simdi + timedelta(seconds=kalan_sn)
    baslangic = bitis - timedelta(hours=kurallar.randevu_suresi(machine_type, program))
    return _yikama(f"demo-{machine_type}", machine_type, makine["machine_no"], program, baslangic, bitis, simdi, demo=True)


def sira_hatasi(student_id, machine_id, baslangic):
    """Bekleme listesine girilebilir mi? Hata mesajı ya da None."""
    makine = db.makine_getir(machine_id)
    if makine is None or makine["laundry_room_id"] != ogrenci_camasirhanesi(student_id) or baslangic <= zaman.simdi():
        return "Bu saat için sıraya girilemez."
    return None
