"""Veritabanı geçişleri (migration).

migrations/ klasöründeki numaralı SQL dosyaları (001_..., 002_...) sırayla, her biri tek bir işlem içinde uygulanır.
Hangi geçişlerin uygulandığı veritabanındaki schema_migrations tablosunda tutulur; böylece şema değişirken
mevcut veri silinmez.

Kullanım:
  python migrations.py                 bekleyen geçişleri uygula (DB_PATH ya da camasirhane.db)
  python migrations.py --durum         uygulanmış / bekleyen geçişleri listele
  python migrations.py --sifirdan      veritabanını silip boştan kur (yalnızca geliştirme: VERİ SİLİNİR)

Yeni bir şema değişikliği için: migrations/ içine bir sonraki numarayla yeni bir dosya ekleyin
(ör. 002_ogrenci_rolu.sql). Uygulanmış bir dosyayı değiştirmeyin: o dosya başka makinelerde zaten çalıştı.
SQLite notu: ALTER TABLE yalnızca sütun ekleyebilir/yeniden adlandırabilir; kısıt değiştirmek için tabloyu
yeni adla kurup veriyi kopyalamak gerekir (bkz. https://www.sqlite.org/lang_altertable.html).
"""
import os
import re
import sqlite3
import sys
from pathlib import Path

import zaman

KLASOR = Path(__file__).parent / "migrations"
DOSYA_ADI = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


class GecisHatasi(Exception):
    pass


def gecisler():
    """[(numara, dosya yolu)] numara sırasıyla. Aynı numara iki kez kullanılmışsa hata."""
    liste = []
    for yol in sorted(KLASOR.iterdir()):
        eslesme = DOSYA_ADI.match(yol.name)
        if eslesme:
            liste.append((int(eslesme.group(1)), yol))
    numaralar = [n for n, _ in liste]
    if len(numaralar) != len(set(numaralar)):
        raise GecisHatasi(f"Aynı numaralı iki geçiş dosyası var: {numaralar}")
    return liste


def _tablolar(conn):
    return {r[0] for r in conn.execute("select name from sqlite_master where type = 'table'")}


def _baslangici_tani(conn):
    """migration sisteminden önce schema.sql ile kurulmuş veritabanı: 001 ile aynıysa 001'i uygulanmış say."""
    tablolar = _tablolar(conn)
    if "schema_migrations" in tablolar or "appointments" not in tablolar:
        return
    sutunlar = {r[1] for r in conn.execute("pragma table_info(appointments)")}
    if "laundry_rooms" not in tablolar or "end_time" not in sutunlar:
        raise GecisHatasi(
            "Bu veritabanı migration sisteminden önceki eski bir şemayla kurulmuş ve 001 ile uyumlu değil.\n"
            "Geliştirme verisiyse yeniden kurun:  python seed.py   (ya da: python migrations.py --sifirdan)")
    conn.execute("create table schema_migrations (version integer primary key, name text not null, applied_at text not null)")
    conn.execute("insert into schema_migrations values (1, '001_baslangic.sql', ?)", (zaman.simdi_metin(),))
    conn.commit()
    print("Mevcut veritabanı 001 ile uyumlu: başlangıç noktası olarak işaretlendi.")


def uygulanmislar(conn):
    if "schema_migrations" not in _tablolar(conn):
        return set()
    return {r[0] for r in conn.execute("select version from schema_migrations")}


def uygula(db_yolu=None, sessiz=False):
    """Bekleyen geçişleri sırayla uygular; uygulanan dosya adlarını döner.
    Bir geçiş hata verirse o geçişin hiçbir değişikliği kalmaz ve GecisHatasi yükselir."""
    db_yolu = db_yolu or os.environ.get("DB_PATH", "camasirhane.db")
    conn = sqlite3.connect(db_yolu)
    conn.isolation_level = None  # BEGIN/COMMIT'i biz yönetiyoruz
    try:
        _baslangici_tani(conn)
        conn.execute("create table if not exists schema_migrations "
                     "(version integer primary key, name text not null, applied_at text not null)")
        yapilmis = uygulanmislar(conn)
        uygulanan = []
        for numara, yol in gecisler():
            if numara in yapilmis:
                continue
            sql = yol.read_text(encoding="utf-8")
            # Geçiş ve kaydı aynı işlemde: ya ikisi birden kalır ya hiçbiri (yarım kalmış şema olmaz).
            # Dosya adı DOSYA_ADI kalıbından geçtiği için ([a-z0-9_]) SQL içine güvenle yazılır.
            kayit = f"insert into schema_migrations values ({numara}, '{yol.name}', '{zaman.simdi_metin()}');"
            try:
                conn.executescript(f"BEGIN;\n{sql}\n;\n{kayit}\nCOMMIT;")
            except sqlite3.Error as e:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise GecisHatasi(f"{yol.name} uygulanamadı, değişiklik geri alındı: {e}") from e
            uygulanan.append(yol.name)
            if not sessiz:
                print(f"Uygulandı: {yol.name}")
        return uygulanan
    finally:
        conn.close()


def durum(db_yolu=None):
    db_yolu = db_yolu or os.environ.get("DB_PATH", "camasirhane.db")
    conn = sqlite3.connect(db_yolu)
    try:
        yapilmis = uygulanmislar(conn)
    finally:
        conn.close()
    for numara, yol in gecisler():
        print(f"{'✓ uygulandı' if numara in yapilmis else '… bekliyor '}  {yol.name}")


if __name__ == "__main__":
    yol = os.environ.get("DB_PATH", "camasirhane.db")
    try:
        if "--durum" in sys.argv:
            durum(yol)
        else:
            if "--sifirdan" in sys.argv and os.path.exists(yol):
                os.remove(yol)
                print(f"{yol} silindi.")
            if not uygula(yol):
                print("Bekleyen geçiş yok, veritabanı güncel.")
    except GecisHatasi as e:
        sys.exit(f"HATA: {e}")
