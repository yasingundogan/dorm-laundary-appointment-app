"""Arayüz kuralları: anonim profil görseli, üst panel, emoji kullanılmaması."""
import glob
import re

import pytest

EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿⬀-⯿️]")


def kayit(client, email, phone):
    client.post("/kayit", data={"first_name": "Deniz", "last_name": "Kaya", "email": email, "phone": phone, "room": "A-1",
                                "password": "password123", "confirm_password": "password123"})
    client.post("/giris", data={"email": email, "password": "password123"})


def test_herkes_icin_tek_anonim_profil_gorseli_ve_cinsiyet_sorulmaz(client, test_db):
    assert "gender" not in client.get("/kayit").get_data(as_text=True)
    kayit(client, "d@test.co", "05550000001")
    html = client.get("/profil").get_data(as_text=True)
    assert html.count('<use href="#avatar"/>') == 2  # üst panel + profil kartı
    assert "gender" not in client.get("/profil/duzenle").get_data(as_text=True)
    sutunlar = {r[1] for r in test_db.execute("PRAGMA table_info(students)")}
    assert "gender" not in sutunlar  # 003: kullanılmayan kişisel veri tutulmaz


def test_makine_numarasinin_yaninda_harf_yok_ve_tip_sembolu_hep_gorunur(client, test_db):
    test_db.execute("INSERT INTO machines (machine_no, machine_type) VALUES (5, 'washer')")
    test_db.execute("INSERT INTO machines (machine_no, machine_type) VALUES (6, 'dryer')")
    test_db.commit()
    kayit(client, "d@test.co", "05550000001")
    html = client.get("/makineler?gun=2026-11-26&saat=10").get_data(as_text=True)
    assert '<span class="no">5</span>' in html and '<span class="no">6</span>' in html
    assert 'class="sembol dalga"' in html and 'class="sembol sicak"' in html  # boş makinelerde de


def test_ust_panel_yazili_baglantilar_ve_adda_r_yok(client, test_db):
    kayit(client, "d@test.co", "05550000001")
    html = client.get("/kayip-esya").get_data(as_text=True)
    assert ">Kayıp eşya</a>" in html and "Bildirimler" in html
    assert 'class="ust-link"\n           aria-current="page">Kayıp eşya' in html  # bulunulan sayfa işaretli
    assert '<span class="brand-ad">DormLaundary App</span>' in html and "tescil" not in html


def test_arayuzde_emoji_yok():
    dosyalar = glob.glob("templates/*.html") + glob.glob("web/*.py") + ["servis.py", "db.py", "kurallar.py"]
    bulunan = [f"{p}:{n}" for p in dosyalar for n, satir in enumerate(open(p, encoding="utf-8"), 1) if EMOJI.search(satir)]
    assert bulunan == []
