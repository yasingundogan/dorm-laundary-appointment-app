"""migrations.py: geçişler sırayla, bir kez ve tek işlemde uygulanır; veri korunur."""
import shutil
import sqlite3

import pytest

import migrations


@pytest.fixture
def gecis_klasoru(tmp_path, monkeypatch):
    """Gerçek geçişlerin kopyası olan geçici bir migrations klasörü; testler buna 9xx numaralı dosyalar ekler."""
    klasor = tmp_path / "migrations"
    klasor.mkdir()
    for yol in migrations.KLASOR.glob("*.sql"):  # gerçek geçişlerin hepsi
        shutil.copy(yol, klasor)
    monkeypatch.setattr(migrations, "KLASOR", klasor)
    return klasor


def hepsi(baslangic=1):
    """Klasördeki geçişlerin adları (baslangic numarasından itibaren): yeni geçiş eklenince testler bozulmaz."""
    return [y.name for n, y in migrations.gecisler() if n >= baslangic]


def tablolar(yol):
    conn = sqlite3.connect(yol)
    try:
        return {r[0] for r in conn.execute("select name from sqlite_master where type = 'table'")}
    finally:
        conn.close()


def test_bos_veritabani_kurulur_ve_ikinci_calistirma_bir_sey_yapmaz(tmp_path):
    yol = str(tmp_path / "t.db")
    assert migrations.uygula(yol, sessiz=True) == hepsi()
    assert {"appointments", "students", "machines", "laundry_rooms", "schema_migrations"} <= tablolar(yol)
    assert migrations.uygula(yol, sessiz=True) == []


def test_yeni_gecis_mevcut_veriyi_silmeden_uygulanir(tmp_path, gecis_klasoru):
    yol = str(tmp_path / "t.db")
    migrations.uygula(yol, sessiz=True)
    conn = sqlite3.connect(yol)
    conn.execute("insert into machines (machine_no, machine_type) values (7, 'washer')")
    conn.commit()
    conn.close()

    (gecis_klasoru / "901_makine_notu.sql").write_text("alter table machines add column note text;")
    assert migrations.uygula(yol, sessiz=True) == ["901_makine_notu.sql"]

    conn = sqlite3.connect(yol)
    assert conn.execute("select machine_no, note from machines").fetchall() == [(7, None)]
    assert [r[0] for r in conn.execute("select version from schema_migrations order by version")][-1] == 901
    conn.close()


def test_hatali_gecis_tamamen_geri_alinir(tmp_path, gecis_klasoru):
    yol = str(tmp_path / "t.db")
    migrations.uygula(yol, sessiz=True)
    # İlk ifade geçerli, ikincisi hatalı: ilk ifadenin etkisi de kalmamalı
    (gecis_klasoru / "901_bozuk.sql").write_text("create table yarim (id integer);\nbu gecerli sql degil;")
    with pytest.raises(migrations.GecisHatasi, match="901_bozuk.sql"):
        migrations.uygula(yol, sessiz=True)
    assert "yarim" not in tablolar(yol)
    conn = sqlite3.connect(yol)
    assert 901 not in [r[0] for r in conn.execute("select version from schema_migrations")]
    conn.close()


def test_ayni_numarali_iki_gecis_reddedilir(gecis_klasoru):
    (gecis_klasoru / "001_baska.sql").write_text("select 1;")
    with pytest.raises(migrations.GecisHatasi, match="Aynı numaralı"):
        migrations.gecisler()


def test_migration_oncesi_kurulmus_uyumlu_veritabani_baslangic_sayilir(tmp_path):
    """schema.sql ile kurulmuş (schema_migrations tablosu olmayan) ama 001 ile aynı veritabanı."""
    yol = str(tmp_path / "eski.db")
    conn = sqlite3.connect(yol)
    conn.executescript((migrations.KLASOR / "001_baslangic.sql").read_text(encoding="utf-8"))
    conn.execute("insert into machines (machine_no, machine_type) values (3, 'dryer')")
    conn.commit()
    conn.close()

    # 001 yeniden çalışmaz (tablolar zaten var); sonraki geçişler veriyi silmeden uygulanır
    assert migrations.uygula(yol, sessiz=True) == hepsi(baslangic=2)
    conn = sqlite3.connect(yol)
    assert conn.execute("select machine_no from machines").fetchall() == [(3,)]
    assert [r[0] for r in conn.execute("select version from schema_migrations order by version")] == \
        [n for n, _ in migrations.gecisler()]
    conn.close()


def test_uyumsuz_eski_veritabani_acik_hata_verir(tmp_path):
    yol = str(tmp_path / "cok_eski.db")
    conn = sqlite3.connect(yol)
    conn.execute("create table appointments (appointment_id integer primary key, start_time text)")
    conn.close()
    with pytest.raises(migrations.GecisHatasi, match="seed.py"):
        migrations.uygula(yol, sessiz=True)
