"""Yurt/blok çamaşırhaneleri, zaman şeridi, arıza bildirme ve kayıp eşya panosu."""
import io
import os
from datetime import datetime, timedelta

import pytest

from app import app
from conftest import randevu_ekle
from kurallar import calisma_saatleri
from servis import gun_seridi
import db
import zaman

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def yarin(saat):
    return (zaman.simdi() + timedelta(days=1)).replace(hour=saat, minute=0, second=0, microsecond=0)


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def kayit_ve_giris(client, email, phone, oda=None):
    data = {"first_name": "Test", "last_name": "Ogrenci", "email": email, "phone": phone,
            "room": "A-1", "password": "password123", "confirm_password": "password123"}
    if oda:
        data["laundry_room_id"] = oda
    client.post("/kayit", data=data)
    client.post("/giris", data={"email": email, "password": "password123"})


@pytest.fixture
def iki_blok(client, test_db, tmp_path, monkeypatch):
    """A Blok (1) ve B Blok (2); her birinde bir çamaşır + bir kurutma. Öğrenci A Blok'ta giriş yapmış."""
    monkeypatch.setitem(app.config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    test_db.execute("INSERT INTO laundry_rooms (laundry_room_id, dorm_name, block_name) VALUES (2, 'Merkez Yurdu', 'B Blok')")
    ids = {}
    for oda in (1, 2):
        for tip in ("washer", "dryer"):
            ids[(oda, tip)] = test_db.execute(
                "INSERT INTO machines (laundry_room_id, machine_no, machine_type) VALUES (?, 1, ?)", (oda, tip)).lastrowid
    test_db.commit()
    kayit_ve_giris(client, "a@test.co", "05550000001", oda=1)
    sid = test_db.execute("SELECT student_id FROM students WHERE student_mail = 'a@test.co'").fetchone()[0]
    return {"client": client, "db": test_db, "m": ids, "sid": sid, "uploads": tmp_path / "uploads"}


# ---- Yurt / blok ----
def test_kayitta_secilen_blok_kaydedilir_ve_secim_zorunlu(client, test_db):
    test_db.execute("INSERT INTO laundry_rooms (laundry_room_id, dorm_name, block_name) VALUES (2, 'Merkez Yurdu', 'B Blok')")
    test_db.commit()
    res = client.post("/kayit", data={"first_name": "A", "last_name": "B", "email": "x@test.co", "phone": "05551112233",
                                      "room": "B-1", "password": "password123", "confirm_password": "password123"})
    assert "Yurdunu ve bloğunu seç" in res.get_data(as_text=True)
    kayit_ve_giris(client, "x@test.co", "05551112233", oda=2)
    assert test_db.execute("SELECT laundry_room_id FROM students").fetchone()[0] == 2


def test_ogrenci_yalnizca_kendi_blogunun_makinelerini_gorur(iki_blok):
    html = iki_blok["client"].get(f"/makineler?gun={yarin(10):%Y-%m-%d}&saat=10").get_data(as_text=True)
    assert f'data-machine-id="{iki_blok["m"][(1, "washer")]}"' in html
    assert f'data-machine-id="{iki_blok["m"][(2, "washer")]}"' not in html
    assert "A Blok çamaşırhanesi" in html


def test_baska_blogun_makinesine_randevu_ve_sira_reddedilir(iki_blok):
    c, d, b_kurutma = iki_blok["client"], iki_blok["db"], iki_blok["m"][(2, "dryer")]
    c.post("/randevu", data={"machine_id": b_kurutma, "start_time": ts(yarin(10))})
    c.post("/sira", data={"machine_id": b_kurutma, "start_time": ts(yarin(10))})
    assert d.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 0
    assert d.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 0


def test_profilden_blok_degistirilir(iki_blok):
    iki_blok["client"].post("/profil/duzenle", data={"first_name": "A", "last_name": "B", "phone": "05550000001",
                                                     "room": "B-2", "laundry_room_id": "2"})
    assert iki_blok["db"].execute("SELECT laundry_room_id FROM students WHERE student_id = ?",
                                  (iki_blok["sid"],)).fetchone()[0] == 2


# ---- Zaman şeridi ----
def test_zaman_seridi_durumlari(iki_blok):
    d, sid, m = iki_blok["db"], iki_blok["sid"], iki_blok["m"]
    gun = yarin(0)
    kapanis = calisma_saatleri(gun)[1]
    b_id = d.execute("INSERT INTO students (student_name, student_surname, student_phone_no, student_mail, room_no,"
                     " student_password_hash) VALUES ('B','B','05550000002','b@test.co','A-2','x')").lastrowid
    randevu_ekle(d, sid, m[(1, "dryer")], yarin(10))
    randevu_ekle(d, b_id, m[(1, "dryer")], yarin(14))

    makineler = db.makineler(1)
    serit = dict(gun_seridi(makineler, 1, gun, zaman.simdi(), sid)[m[(1, "dryer")]])
    assert serit[10] == serit[11] == "benim"          # 2 saatlik kendi kurutması
    assert serit[14] == serit[15] == "dolu"           # başkasının
    assert serit[13] == "bos"                         # 13:00 boş ama 2 saat sığmıyor (14:00 dolu)
    assert serit[12] == "uygun"
    assert serit[kapanis - 1] == "bos"                # kapanıştan 1 saat önce kurutma başlamaz
    assert dict(gun_seridi(makineler, 1, gun, zaman.simdi(), sid)[m[(1, "washer")]])[kapanis - 1] == "uygun"


def test_arizali_makine_seritte_arizali(iki_blok):
    d, m = iki_blok["db"], iki_blok["m"]
    d.execute("UPDATE machines SET out_of_order = 1 WHERE machine_id = ?", (m[(1, "washer")],))
    d.commit()
    serit = gun_seridi(db.makineler(1), 1, yarin(0), zaman.simdi(), None)
    assert {durum for _, durum in serit[m[(1, "washer")]]} == {"ariza"}


# ---- Arıza bildirme ----
def test_fotografli_ariza_bildirimi_kaydedilir(iki_blok):
    c, d, mid = iki_blok["client"], iki_blok["db"], iki_blok["m"][(1, "washer")]
    res = c.post(f"/makine/{mid}/ariza", content_type="multipart/form-data",
                 data={"description": "Su boşaltmıyor", "photo": (io.BytesIO(PNG), "foto.png")})
    assert res.status_code == 302
    row = d.execute("SELECT * FROM fault_reports").fetchone()
    assert row["description"] == "Su boşaltmıyor" and row["photo_path"].endswith(".png")
    assert (iki_blok["uploads"] / row["photo_path"]).read_bytes() == PNG
    # Kartta "arıza bildirildi" görünür
    assert "Arıza bildirildi" in c.get(f"/makineler?gun={yarin(10):%Y-%m-%d}&saat=10").get_data(as_text=True)


def test_resim_olmayan_dosya_reddedilir(iki_blok):
    mid = iki_blok["m"][(1, "washer")]
    res = iki_blok["client"].post(f"/makine/{mid}/ariza", content_type="multipart/form-data",
                                  data={"description": "Su boşaltmıyor", "photo": (io.BytesIO(b"<script>"), "foto.jpg")})
    assert res.status_code == 400 and "JPG, PNG ya da WEBP" in res.get_data(as_text=True)
    assert iki_blok["db"].execute("SELECT COUNT(*) FROM fault_reports").fetchone()[0] == 0


def test_ayni_makineye_ikinci_acik_bildirim_reddedilir_ve_fotografi_silinir(iki_blok):
    c, mid = iki_blok["client"], iki_blok["m"][(1, "washer")]
    c.post(f"/makine/{mid}/ariza", data={"description": "Çalışmıyor"})
    res = c.post(f"/makine/{mid}/ariza", content_type="multipart/form-data",
                 data={"description": "Hâlâ çalışmıyor", "photo": (io.BytesIO(PNG), "foto.png")})
    assert res.status_code == 400
    assert iki_blok["db"].execute("SELECT COUNT(*) FROM fault_reports").fetchone()[0] == 1
    assert not os.listdir(iki_blok["uploads"])  # kaydedilmeyen bildirimin fotoğrafı diskte kalmaz


@pytest.mark.parametrize("aciklama", ["", "abc", "x" * 501])
def test_ariza_aciklamasi_5_500_karakter(iki_blok, aciklama):
    res = iki_blok["client"].post(f"/makine/{iki_blok['m'][(1, 'washer')]}/ariza", data={"description": aciklama})
    assert res.status_code == 400


def test_baska_blogun_makinesine_ariza_bildirilemez(iki_blok):
    assert iki_blok["client"].post(f"/makine/{iki_blok['m'][(2, 'washer')]}/ariza",
                                   data={"description": "Çalışmıyor"}).status_code == 404


# ---- Kayıp eşya ----
def test_kayip_esya_ilani_yalnizca_kendi_blogunda_gorunur(iki_blok):
    c = iki_blok["client"]
    c.post("/kayip-esya", data={"description": "Mavi çizgili çorap", "machine_id": iki_blok["m"][(1, "washer")]})
    html = c.get("/kayip-esya").get_data(as_text=True)
    assert "Mavi çizgili çorap" in html and "Çamaşır makinesi 1" in html

    from app import app as uygulama
    b = uygulama.test_client()
    kayit_ve_giris(b, "b@test.co", "05550000002", oda=2)
    assert "Mavi çizgili çorap" not in b.get("/kayip-esya").get_data(as_text=True)


def test_kayip_esya_ilanini_yalnizca_veren_kapatir(iki_blok):
    c, d = iki_blok["client"], iki_blok["db"]
    c.post("/kayip-esya", data={"description": "Beyaz havlu"})
    item = d.execute("SELECT item_id FROM lost_items").fetchone()[0]

    from app import app as uygulama
    b = uygulama.test_client()
    kayit_ve_giris(b, "b@test.co", "05550000002", oda=1)
    b.post(f"/kayip-esya/{item}/kapat")
    assert d.execute("SELECT resolved_at FROM lost_items").fetchone()[0] is None

    c.post(f"/kayip-esya/{item}/kapat")
    assert d.execute("SELECT resolved_at FROM lost_items").fetchone()[0] is not None
    assert "Beyaz havlu" not in c.get("/kayip-esya").get_data(as_text=True)


def test_baska_blogun_makinesi_ilana_eklenemez(iki_blok):
    iki_blok["client"].post("/kayip-esya", data={"description": "Siyah tişört", "machine_id": iki_blok["m"][(2, "washer")]})
    assert iki_blok["db"].execute("SELECT machine_id FROM lost_items").fetchone()[0] is None
