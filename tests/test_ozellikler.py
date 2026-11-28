"""İptal, bildirimler, bekleme listesi, kurutma önerisi ve profil düzenleme.
Tarihler bugüne göre hesaplanır: testler takvim ilerledikçe bozulmaz."""
from datetime import datetime, timedelta

import pytest

from app import app
from conftest import randevu_ekle as _randevu_ekle
from kurallar import calisma_saatleri
import zaman


def yarin(saat):
    return (zaman.simdi() + timedelta(days=1)).replace(hour=saat, minute=0, second=0, microsecond=0)


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def kayit_ve_giris(client, email, phone):
    client.post("/kayit", data={
        "first_name": "Test", "last_name": "Ogrenci", "email": email, "phone": phone,
        "room": "A-1", "password": "password123", "confirm_password": "password123",
    })
    client.post("/giris", data={"email": email, "password": "password123"})


@pytest.fixture
def ortam(client, test_db):
    """Giriş yapmış öğrenci A + birer çamaşır ve kurutma makinesi."""
    kayit_ve_giris(client, "a@test.co", "05550000001")
    w = test_db.execute("INSERT INTO machines (machine_no, machine_type) VALUES (1, 'washer')").lastrowid
    d = test_db.execute("INSERT INTO machines (machine_no, machine_type) VALUES (1, 'dryer')").lastrowid
    test_db.commit()
    a_id = test_db.execute("SELECT student_id FROM students WHERE student_mail = 'a@test.co'").fetchone()[0]
    return {"client": client, "db": test_db, "washer": w, "dryer": d, "a": a_id}


def randevu_ekle(db, student_id, machine_id, start, program=None):
    return _randevu_ekle(db, student_id, machine_id, start, program)


# ---- 1. İptal ----
def test_kendi_gelecek_randevusunu_iptal_edebilir(ortam):
    rid = randevu_ekle(ortam["db"], ortam["a"], ortam["dryer"], yarin(10))
    res = ortam["client"].post(f"/randevu/{rid}/iptal")
    assert res.status_code == 302
    row = ortam["db"].execute("SELECT status, cancelled_at FROM appointments WHERE appointment_id = ?", (rid,)).fetchone()
    assert row["status"] == "cancelled" and row["cancelled_at"]


def test_baskasinin_randevusu_iptal_edilemez(ortam, test_db):
    b_id = test_db.execute(
        "INSERT INTO students (student_name, student_surname, student_phone_no, student_mail, room_no, student_password_hash)"
        " VALUES ('B', 'B', '05550000002', 'b@test.co', 'B-1', 'x')").lastrowid
    rid = randevu_ekle(test_db, b_id, ortam["dryer"], yarin(10))
    assert ortam["client"].post(f"/randevu/{rid}/iptal").status_code == 404
    assert test_db.execute("SELECT status FROM appointments WHERE appointment_id = ?", (rid,)).fetchone()[0] == "active"


def test_baslamis_randevu_iptal_edilemez(ortam):
    rid = randevu_ekle(ortam["db"], ortam["a"], ortam["dryer"], zaman.simdi() - timedelta(minutes=30))
    ortam["client"].post(f"/randevu/{rid}/iptal")
    assert ortam["db"].execute("SELECT status FROM appointments WHERE appointment_id = ?", (rid,)).fetchone()[0] == "active"


# ---- 7. Bekleme listesi ----
def test_iptal_edilen_saati_bekleyen_bildirim_alir(ortam):
    db = ortam["db"]
    # A'nın 14:00-16:00 kurutması, 15:00 başlangıcını da kapatır
    rid = randevu_ekle(db, ortam["a"], ortam["dryer"], yarin(14))

    b = app.test_client()
    kayit_ve_giris(b, "b@test.co", "05550000002")
    b.post("/sira", data={"machine_id": ortam["dryer"], "start_time": ts(yarin(15))})
    assert db.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 1

    ortam["client"].post(f"/randevu/{rid}/iptal")

    bildirim = db.execute("SELECT s.student_mail, n.kind, n.message FROM notifications n "
                          "JOIN students s USING (student_id)").fetchall()
    assert [(r[0], r[1]) for r in bildirim] == [("b@test.co", "sira")]
    assert yarin(15).strftime("%H:%M") in bildirim[0][2]
    assert db.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 0  # bilgilendirilen sıradan çıkar


def test_siradan_cikilabilir(ortam):
    data = {"machine_id": ortam["dryer"], "start_time": ts(yarin(15))}
    ortam["client"].post("/sira", data=data)
    ortam["client"].post("/sira", data={**data, "islem": "cik"})
    assert ortam["db"].execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 0


def test_gecmis_saat_icin_siraya_girilemez(ortam):
    ortam["client"].post("/sira", data={"machine_id": ortam["dryer"], "start_time": ts(zaman.simdi() - timedelta(hours=1))})
    assert ortam["db"].execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 0


# ---- 4. Bildirimler ----
def test_hatirlatma_ve_bitti_bildirimleri_bir_kez_uretilir(ortam):
    db, simdi = ortam["db"], zaman.simdi()
    randevu_ekle(db, ortam["a"], ortam["dryer"], simdi + timedelta(minutes=20))                   # hatırlatma
    randevu_ekle(db, ortam["a"], ortam["washer"], simdi - timedelta(minutes=90), "colored")       # renkli 1 saat: 30 dk önce bitti
    randevu_ekle(db, ortam["a"], ortam["washer"], simdi - timedelta(days=3), "white")             # çok eski: bildirim yok

    ortam["client"].get("/makineler")
    ortam["client"].get("/makineler")  # ikinci ziyaret tekrar üretmez
    turler = sorted(r[0] for r in db.execute("SELECT kind FROM notifications"))
    assert turler == ["bitti", "hatirlatma"]


def test_bildirimler_sayfasi_okundu_yapar_ve_rozet_kaybolur(ortam):
    randevu_ekle(ortam["db"], ortam["a"], ortam["dryer"], zaman.simdi() + timedelta(minutes=20))
    html = ortam["client"].get("/makineler").get_data(as_text=True)
    assert 'class="rozet-sayi"' in html

    html = ortam["client"].get("/bildirimler").get_data(as_text=True)
    assert "30 dakika içinde başlıyor" in html
    assert ortam["db"].execute("SELECT COUNT(*) FROM notifications WHERE read_at IS NULL").fetchone()[0] == 0
    assert 'class="rozet-sayi"' not in ortam["client"].get("/makineler").get_data(as_text=True)


# ---- 9. Kurutma önerisi ----
def test_camasir_randevusundan_sonra_kurutma_onerilir(ortam):
    res = ortam["client"].post("/randevu", follow_redirects=True, data={
        "machine_id": ortam["washer"], "start_time": ts(yarin(10)), "program": "white"})
    html = res.get_data(as_text=True)
    assert "Randevun alındı." in html
    assert "Kurutma makinesi seç" in html and "saat=11" in html and "#kurutma" in html


def test_kapanisa_yetismeyecek_kurutma_onerilmez(ortam):
    kapanis = calisma_saatleri(yarin(0))[1]
    res = ortam["client"].post("/randevu", follow_redirects=True, data={
        "machine_id": ortam["washer"], "start_time": ts(yarin(kapanis - 1)), "program": "colored"})
    html = res.get_data(as_text=True)
    assert "Randevun alındı." in html and "Kurutma makinesi seç" not in html


# ---- 10. Profil düzenleme ----
def test_profil_bilgileri_guncellenir(ortam):
    res = ortam["client"].post("/profil/duzenle", data={
        "first_name": " Ayşe ", "last_name": "Yıldız", "phone": "0555 999 88 77", "room": "C-3",
        "email": "hack@test.co"})  # e-posta değiştirilemez, yok sayılır
    assert res.status_code == 302
    row = ortam["db"].execute("SELECT * FROM students WHERE student_id = ?", (ortam["a"],)).fetchone()
    assert (row["student_name"], row["student_phone_no"], row["room_no"], row["student_mail"]) == \
           ("Ayşe", "05559998877", "C-3", "a@test.co")
    with ortam["client"].session_transaction() as sess:
        assert sess["student_name"] == "Ayşe"


@pytest.mark.parametrize("degisiklik, hata", [
    ({"phone": "05550000002"}, "başka bir hesapta"),   # B'nin telefonu
    ({"room": "  "}, "Boş alan"),
    ({"phone": "123"}, "10-15 rakam"),
])
def test_profil_gecersiz_bilgi_reddedilir(ortam, degisiklik, hata):
    kayit_ve_giris(app.test_client(), "b@test.co", "05550000002")
    data = {"first_name": "A", "last_name": "B", "phone": "05550000001", "room": "A-1", **degisiklik}
    res = ortam["client"].post("/profil/duzenle", data=data)
    assert res.status_code == 200 and hata in res.get_data(as_text=True)
    assert ortam["db"].execute("SELECT room_no FROM students WHERE student_id = ?", (ortam["a"],)).fetchone()[0] == "A-1"


# ---- Beyaz ve renkli yıkama 1 saat ----
def test_beyaz_yikama_bir_saat_surer(ortam):
    c, db = ortam["client"], ortam["db"]
    res = c.post("/randevu", follow_redirects=True, data={
        "machine_id": ortam["washer"], "start_time": ts(yarin(10)), "program": "white"})
    html = res.get_data(as_text=True)
    assert "Randevun alındı." in html and "saat=11" in html  # kurutma önerisi beyaz bitince: 11:00

    # 11:00 hemen boş: başka öğrenci alabilir
    from app import app
    b = app.test_client()
    b.post("/kayit", data={"first_name": "B", "last_name": "B", "email": "b@test.co", "phone": "05550000002",
                           "room": "A-2", "password": "password123", "confirm_password": "password123"})
    b.post("/giris", data={"email": "b@test.co", "password": "password123"})
    b.post("/randevu", data={"machine_id": ortam["washer"], "start_time": ts(yarin(11)), "program": "colored"})
    saatler = [r[0][11:13] for r in db.execute("SELECT start_time FROM appointments ORDER BY start_time")]
    assert saatler == ["10", "11"]


def test_kapanistan_bir_saat_once_beyaz_alinir(ortam):
    kapanis = calisma_saatleri(yarin(0))[1]
    res = ortam["client"].post("/randevu", follow_redirects=True, data={
        "machine_id": ortam["washer"], "start_time": ts(yarin(kapanis - 1)), "program": "white"})
    assert "Randevun alındı." in res.get_data(as_text=True)


def test_bos_saatte_beyaz_secenegi_acik(ortam):
    # 11:00 dolu: 10:00'da beyaz da olur (1 saat, 10-11)
    randevu_ekle(ortam["db"], ortam["a"], ortam["washer"], yarin(11), "colored")
    html = ortam["client"].get(f"/makineler?gun={yarin(10):%Y-%m-%d}&saat=10").get_data(as_text=True)
    assert 'data-saat="10"\n                          data-beyaz="1"' in html


# ---- Çamaşır durum penceresi (ana ekranın altı) ----
def _gun(saat, dakika=0):
    return zaman.simdi().replace(hour=saat, minute=dakika, second=0)  # sabit an: 25.11.2026 12:00


def test_calisan_camasir_icin_durum_penceresi_cikar(ortam):
    randevu_ekle(ortam["db"], ortam["a"], ortam["washer"], _gun(11, 30), "white")  # 11:30-12:30, 30 dk kaldı
    html = ortam["client"].get("/makineler").get_data(as_text=True)
    assert 'id="yikama"' in html and 'data-kalan="1800"' in html and 'data-toplam="3600"' in html
    assert "Çamaşır makinesi 1 · Beyaz" in html and "Makine çalışıyor" in html and "ikon-washer" in html
    assert "Bitiş <strong>12:30</strong>" in html


def test_biten_kurutma_30_dakika_hazir_gorunur_sonra_kaybolur(ortam):
    randevu_ekle(ortam["db"], ortam["a"], ortam["dryer"], _gun(9, 50))  # 09:50-11:50: 10 dk önce bitti
    html = ortam["client"].get("/makineler").get_data(as_text=True)
    assert 'class="yikama dryer bitti"' in html and "Program tamamlandı" in html and "ikon-dryer" in html

    ortam["db"].execute("DELETE FROM notifications")  # ilk ziyaret "çamaşırın hazır" bildirimi üretti
    ortam["db"].execute("DELETE FROM appointments")
    randevu_ekle(ortam["db"], ortam["a"], ortam["dryer"], _gun(9))  # 09:00-11:00: 1 saat önce bitti
    assert 'id="yikama"' not in ortam["client"].get("/makineler").get_data(as_text=True)


def test_gelecekteki_randevu_icin_pencere_cikmaz(ortam):
    randevu_ekle(ortam["db"], ortam["a"], ortam["washer"], _gun(15), "colored")
    assert 'id="yikama"' not in ortam["client"].get("/makineler").get_data(as_text=True)


def test_deneme_modu_yalnizca_aciksa_calisir(ortam, monkeypatch):
    c = ortam["client"]
    monkeypatch.setitem(app.config, "DEMO_ACIK", False)
    assert 'id="yikama"' not in c.get("/makineler?demo=dryer").get_data(as_text=True)

    monkeypatch.setitem(app.config, "DEMO_ACIK", True)
    html = c.get("/makineler?demo=dryer&kalan=15").get_data(as_text=True)
    assert 'data-kalan="15"' in html and "Kurutma makinesi 1" in html and ">Test<" in html
    assert ortam["db"].execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 0  # veritabanına yazılmaz


def test_durum_penceresi_profilde_de_gorunur(ortam):
    randevu_ekle(ortam["db"], ortam["a"], ortam["washer"], _gun(11, 30), "white")
    html = ortam["client"].get("/profil").get_data(as_text=True)
    assert 'id="yikama"' in html and 'data-kalan="1800"' in html
