"""kurallar.py ve zaman.py: sunucu ve veritabanı olmadan test edilen saf kurallar."""
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import kurallar
import zaman

CARSAMBA_OGLE = datetime(2026, 11, 25, 12, 0)
YIKAMA = {"machine_id": 1, "machine_type": "washer", "laundry_room_id": 1, "out_of_order": 0}
KURUTMA = {**YIKAMA, "machine_type": "dryer"}


@pytest.mark.parametrize("tip, program, saat", [("washer", "colored", 1), ("washer", "white", 2), ("dryer", None, 2)])
def test_randevu_suresi(tip, program, saat):
    assert kurallar.randevu_suresi(tip, program) == saat


@pytest.mark.parametrize("makine, oda, baslangic, program, hata", [
    (None, 1, datetime(2026, 11, 26, 10), "white", "bulunamadı"),
    (YIKAMA, 2, datetime(2026, 11, 26, 10), "white", "çamaşırhanende değil"),
    (YIKAMA, 1, datetime(2026, 11, 25, 11), "white", "Geçmiş"),
    (YIKAMA, 1, datetime(2026, 12, 7, 10), "white", "06.12.2026"),           # pencere gelecek pazar biter
    (YIKAMA, 1, datetime(2026, 11, 28, 8), "white", "09:00-17:00"),          # cumartesi 09:00'da açılır
    (YIKAMA, 1, datetime(2026, 11, 26, 19), "white", "21:00'de biterdi"),    # beyaz 2 saat: kapanışı aşar
    (YIKAMA, 1, datetime(2026, 11, 26, 19), "colored", None),                # renkli 1 saat: sığar
    (KURUTMA, 1, datetime(2026, 11, 26, 19), None, "21:00'de biterdi"),
    ({**YIKAMA, "out_of_order": 1}, 1, datetime(2026, 11, 26, 10), "white", "arızalı"),
    (YIKAMA, 1, datetime(2026, 11, 26, 10), None, "program seçmelisin"),
    (KURUTMA, 1, datetime(2026, 11, 26, 10), None, None),
])
def test_randevu_hatasi(makine, oda, baslangic, program, hata):
    sonuc = kurallar.randevu_hatasi(makine, oda, baslangic, program, CARSAMBA_OGLE)
    assert (sonuc is None) if hata is None else (hata in sonuc)


@pytest.mark.parametrize("gun, son", [
    (datetime(2026, 11, 23), "2026-12-06"),  # pazartesi
    (datetime(2026, 11, 29), "2026-12-06"),  # pazar: hâlâ gelecek haftanın pazarı
    (datetime(2026, 11, 30), "2026-12-13"),  # yeni hafta: pencere bir hafta kayar
])
def test_son_rezervasyon_gunu(gun, son):
    assert str(kurallar.son_rezervasyon_gunu(gun)) == son


def test_beyaz_ancak_iki_bos_saate_sigar():
    hucreler = [(8, "uygun"), (9, "uygun"), (10, "dolu"), (11, "uygun"), (19, "uygun")]
    assert kurallar.beyaz_sigan_saatler(hucreler) == {8}


def test_serit_hesapla_kendi_ve_baskasinin_randevusu():
    gun = datetime(2026, 11, 26)
    randevular = [(1, gun.replace(hour=10), gun.replace(hour=12), 7), (1, gun.replace(hour=14), gun.replace(hour=15), 8)]
    serit = dict(kurallar.serit_hesapla([KURUTMA], randevular, gun, CARSAMBA_OGLE, student_id=7)[1])
    assert (serit[10], serit[11]) == ("benim", "benim")   # kendi 2 saatlik kurutması
    assert serit[14] == "dolu"                            # başkasının
    assert serit[12] == "uygun"                           # 12-14 sığar: 14:00'teki randevu tam bitişte başlar
    assert serit[13] == "bos"                             # 13-15 sığmaz: 14:00 dolu
    assert serit[19] == "bos"                             # kapanışa yetişmez
    assert serit[16] == "uygun"


@pytest.mark.parametrize("veri, uzanti", [
    (b"\xff\xd8\xff\xe0" + b"0" * 20, "jpg"), (b"\x89PNG\r\n\x1a\n" + b"0" * 20, "png"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"), (b"<script>alert(1)</script>", None),
])
def test_foto_uzantisi_icerige_bakar(veri, uzanti):
    assert kurallar.foto_uzantisi(veri) == uzanti


# ---- Kayıtlı bitiş saati ----
def test_randevunun_bitisi_programa_gore_kaydedilir(client, test_db):
    w = test_db.execute("INSERT INTO machines (machine_no, machine_type) VALUES (1, 'washer')").lastrowid
    test_db.commit()
    client.post("/kayit", data={"first_name": "A", "last_name": "B", "email": "a@t.co", "phone": "05550000001",
                                "room": "A-1", "password": "password123", "confirm_password": "password123"})
    client.post("/giris", data={"email": "a@t.co", "password": "password123"})
    client.post("/randevu", data={"machine_id": w, "start_time": "2026-11-26 10:00:00", "program": "white"})
    client.post("/randevu", data={"machine_id": w, "start_time": "2026-11-27 10:00:00", "program": "colored"})
    satirlar = test_db.execute("SELECT start_time, end_time, created_at FROM appointments ORDER BY start_time").fetchall()
    assert [(r[0], r[1]) for r in satirlar] == [("2026-11-26 10:00:00", "2026-11-26 12:00:00"),
                                               ("2026-11-27 10:00:00", "2026-11-27 11:00:00")]
    assert {r[2] for r in satirlar} == {"2026-11-25 12:00:00"}  # kayıt saati de zaman.simdi()'den


# ---- Zaman ----
def test_simdi_sunucunun_saat_diliminden_bagimsiz_istanbul_saatidir(monkeypatch):
    monkeypatch.undo()  # bu testte sabit zaman değil, gerçek zaman.simdi
    eski = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "UTC"  # ör. UTC'de çalışan bir bulut sunucusu
        time.tzset()
        istanbul = datetime.now(ZoneInfo("Europe/Istanbul")).replace(tzinfo=None)
        assert abs(zaman.simdi() - istanbul) < timedelta(seconds=5)
        assert abs(zaman.simdi() - datetime.now()) > timedelta(hours=2)  # sunucu saati (UTC) kullanılmadı
    finally:
        if eski is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = eski
        time.tzset()


def test_yikama_durumu():
    bas, bit = datetime(2026, 11, 25, 11), datetime(2026, 11, 25, 13)
    assert kurallar.yikama_durumu(bas, bit, datetime(2026, 11, 25, 12)) == \
        {"toplam_sn": 7200, "kalan_sn": 3600, "ilerleme": 0.5, "bitti": False}
    assert kurallar.yikama_durumu(bas, bit, datetime(2026, 11, 25, 13, 5))["bitti"] is True
