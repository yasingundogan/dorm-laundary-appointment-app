import threading
from datetime import datetime, timedelta

import pytest

from app import app
from conftest import randevu_ekle
import zaman


def kayit_ve_giris(client, email, phone):
    client.post("/kayit", data={
        "first_name": "Test", "last_name": "Ogrenci", "email": email, "phone": phone,
        "room": "A-1", "password": "password123", "confirm_password": "password123",
    })
    client.post("/giris", data={"email": email, "password": "password123"})


# ---- CSRF ----
def test_csrf_tokensiz_post_reddedilir(client):
    app.config["CSRF_ACIK"] = True
    try:
        assert client.post("/giris", data={"email": "a@b.co", "password": "x"}).status_code == 400

        client.get("/giris")  # sayfa token'ı oturuma yazar
        with client.session_transaction() as sess:
            token = sess["csrf"]
        res = client.post("/giris", data={"email": "a@b.co", "password": "x", "csrf": token})
        assert res.status_code == 200  # token doğru: istek işlendi (bilgiler hatalı)
    finally:
        app.config["CSRF_ACIK"] = False


def test_cikis_get_ile_yapilamaz(client):
    assert client.get("/cikis").status_code == 405


# ---- Giriş deneme sınırı ----
def test_bes_hatali_denemeden_sonra_giris_kilitlenir(client, registered_student):
    email = registered_student["email"]
    for _ in range(5):
        assert client.post("/giris", data={"email": email, "password": "yanlis"}).status_code == 200
    # 6. deneme doğru şifreyle bile kilitli
    res = client.post("/giris", data={"email": email, "password": registered_student["password"]})
    assert res.status_code == 429
    with client.session_transaction() as sess:
        assert "student_id" not in sess


# ---- Kayıt girdileri ----
def test_eposta_kucuk_harfe_cevrilir_ve_bosluklar_atilir(client, test_db):
    kayit_ve_giris(client, "  Ali@Ogrenci.EDU.tr ", "0555 111 22 33")
    row = test_db.execute("SELECT student_mail, student_phone_no FROM students").fetchone()
    assert (row["student_mail"], row["student_phone_no"]) == ("ali@ogrenci.edu.tr", "05551112233")

    res = client.post("/giris", data={"email": "ALI@ogrenci.edu.tr", "password": "password123"})
    assert res.status_code == 302


@pytest.mark.parametrize("alan, deger", [("email", "eposta-degil"), ("email", "a@b"), ("phone", "12345"), ("phone", "abc5551112233")])
def test_gecersiz_eposta_ve_telefon_reddedilir(client, test_db, alan, deger):
    data = {"first_name": "A", "last_name": "B", "email": "a@b.co", "phone": "05551112233",
            "room": "A-1", "password": "password123", "confirm_password": "password123", alan: deger}
    assert client.post("/kayit", data=data).status_code == 200
    assert test_db.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0


# ---- Aynı anda gelen çakışan randevular ----
def test_ayni_anda_gelen_cakisan_kurutma_randevularindan_yalnizca_biri_kaydedilir(client, test_db):  # client: CSRF kapalı test ayarı
    d_id = test_db.execute("INSERT INTO machines (machine_no, machine_type) VALUES (1, 'dryer')").lastrowid
    test_db.commit()
    yarin = (zaman.simdi() + timedelta(days=1)).strftime("%Y-%m-%d")

    istemciler = [app.test_client() for _ in range(2)]
    for i, c in enumerate(istemciler):
        kayit_ve_giris(c, f"ogr{i}@test.co", f"0555000000{i}")

    # 14:00-16:00 ve 15:00-17:00 aynı makinede çakışır; başlangıçları farklı olduğu için benzersizlik kuralı yakalamaz
    baslangiclar = [f"{yarin} 14:00:00", f"{yarin} 15:00:00"]
    bariyer = threading.Barrier(2)

    def gonder(c, saat):
        bariyer.wait()
        c.post("/randevu", data={"machine_id": d_id, "start_time": saat})

    for _ in range(5):  # yarışı birkaç kez dene
        test_db.execute("DELETE FROM appointments")
        test_db.commit()
        threads = [threading.Thread(target=gonder, args=a) for a in zip(istemciler, baslangiclar)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert test_db.execute("SELECT COUNT(*) FROM appointments WHERE status = 'active'").fetchone()[0] == 1


# ---- Süresi dolan randevular ----
def test_suresi_dolan_randevu_tamamlandi_olur(client, registered_student, test_db):
    w_id = test_db.execute("INSERT INTO machines (machine_no, machine_type) VALUES (1, 'washer')").lastrowid
    s_id = test_db.execute("SELECT student_id FROM students").fetchone()[0]
    gecmis = (zaman.simdi() - timedelta(hours=2)).replace(minute=0, second=0)
    gelecek = (zaman.simdi() + timedelta(days=1)).replace(hour=10, minute=0, second=0)
    for t in (gecmis, gelecek):
        randevu_ekle(test_db, s_id, w_id, t, "white")
    gecmis, gelecek = zaman.metin(gecmis), zaman.metin(gelecek)

    client.get("/makineler")
    durumlar = dict(test_db.execute("SELECT start_time, status FROM appointments").fetchall())
    assert durumlar == {gecmis: "completed", gelecek: "active"}
