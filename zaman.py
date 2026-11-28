"""Uygulamanın tek zaman kaynağı.

Çamaşırhane Türkiye'de: sunucu hangi saat diliminde çalışırsa çalışsın (ör. UTC'deki bir bulut sunucusu)
"şimdi" her zaman İstanbul saatidir. Veritabanında saatler 'YYYY-MM-DD HH:MM:SS' metni olarak,
İstanbul yerel saatiyle (saat dilimi bilgisi olmadan) tutulur.

Kodun hiçbir yerinde datetime.now() ya da SQL'de datetime('now') kullanılmaz; hepsi buradan geçer.
Testler zaman.simdi'yi sabit bir ana bağlar (tests/conftest.py), böylece takvim ilerledikçe bozulmazlar.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

SAAT_DILIMI = ZoneInfo("Europe/Istanbul")
BICIM = "%Y-%m-%d %H:%M:%S"


def simdi():
    """İstanbul'da şu an (saat dilimi bilgisi atılmış; veritabanındaki saatlerle doğrudan karşılaştırılabilir)."""
    return datetime.now(SAAT_DILIMI).replace(tzinfo=None, microsecond=0)


def metin(an):
    """datetime -> veritabanı biçimi."""
    return an.strftime(BICIM)


def oku(deger):
    """Veritabanı biçimi -> datetime. Geçersizse ValueError."""
    return datetime.strptime(deger, BICIM)


def simdi_metin():
    return metin(simdi())
