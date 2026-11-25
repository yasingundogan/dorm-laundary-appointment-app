"""Çamaşırhane iş kuralları: saf fonksiyonlar.

Bu dosya veritabanına, Flask'a ve "şimdi"ye bağımlı değildir: her şey parametre olarak gelir.
Böylece kurallar sunucu çalıştırmadan test edilir; web sayfası, görevli paneli ya da ileride bir API
aynı kuralları kullanır. Veritabanı gerektiren adımlar (haftalık hak, çakışma) servis.py'dedir.
"""
import re
from datetime import timedelta

HAFTALIK_CAMASIR_HAKKI = 2

# Randevu süreleri (saat). Tek kaynak: Python bunları kullanır, randevunun bitişi (end_time) bunlarla
# hesaplanıp veritabanına yazılır, sayfadaki JavaScript de aynı tabloyu sunucudan alır.
SURELER = {"dryer": 2, "white": 2, "colored": 1}
PROGRAMLAR = ("colored", "white")

EPOSTA_KALIBI = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
TELEFON_KALIBI = re.compile(r"\+?\d{10,15}")

FOTO_SINIRI = 5 * 1024 * 1024
# Uzantıya değil dosyanın ilk baytlarına bakılır: "foto.jpg" adlı başka bir dosya kabul edilmez
FOTO_IMZALARI = {b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}


# ---- Süre ve çalışma saatleri ----

def randevu_suresi(machine_type, program):
    """Saat cinsinden süre: kurutma ve beyaz yıkama 2 saat, renkli yıkama 1 saat."""
    return SURELER["dryer"] if machine_type == "dryer" else SURELER.get(program, SURELER["colored"])


def bitis_saati(baslangic, machine_type, program):
    return baslangic + timedelta(hours=randevu_suresi(machine_type, program))


def calisma_saatleri(gun):
    """(açılış, kapanış) saati: hafta içi 08-20, hafta sonu 09-17."""
    return (9, 17) if gun.weekday() >= 5 else (8, 20)


def son_rezervasyon_gunu(simdi):
    """En ileri randevu günü: gelecek haftanın pazarı. Bu hafta içinde gelecek haftaya da yer ayırtılabilir."""
    return (simdi + timedelta(days=6 - simdi.weekday() + 7)).date()


def baslangic_saatleri(gun, simdi):
    """O gün randevu başlatılabilecek, henüz geçmemiş tam saatler."""
    acilis, kapanis = calisma_saatleri(gun)
    gun = gun.replace(hour=0, minute=0, second=0, microsecond=0)
    return [s for s in range(acilis, kapanis) if gun.replace(hour=s) > simdi]


def secilebilir_gunler(simdi):
    """Bugünden gelecek haftanın pazarına kadar, en az bir boş saati kalan günler."""
    bugun = simdi.replace(hour=0, minute=0, second=0, microsecond=0)
    gun_sayisi = (son_rezervasyon_gunu(simdi) - bugun.date()).days + 1
    return [g for g in (bugun + timedelta(days=i) for i in range(gun_sayisi)) if baslangic_saatleri(g, simdi)]


def hafta_araligi(gun):
    """gun'ün içinde olduğu pazartesi-pazar haftası: (pazartesi, pazar)."""
    pazartesi = gun - timedelta(days=gun.weekday())
    return pazartesi, pazartesi + timedelta(days=6)


# ---- Randevu kuralları ----

def randevu_hatasi(makine, ogrenci_camasirhanesi, baslangic, program, simdi):
    """Veritabanı gerektirmeyen randevu kuralları. Hata mesajı ya da (geçerliyse) None döner.
    Haftalık hak ve çakışma kontrolleri servis.randevu_olustur'da, kayıtla aynı kilitli işlemde yapılır."""
    if makine is None:
        return "Makine bulunamadı."
    if makine["laundry_room_id"] != ogrenci_camasirhanesi:
        return "Bu makine senin çamaşırhanende değil."
    if baslangic < simdi:
        return "Geçmiş bir saate randevu alınamaz."
    son_gun = son_rezervasyon_gunu(simdi)
    if baslangic.date() > son_gun:
        return f"En fazla {son_gun:%d.%m.%Y} tarihine kadar randevu alınabilir."

    acilis, kapanis = calisma_saatleri(baslangic)
    if baslangic.hour < acilis:
        return f"Çamaşırhane bu gün {acilis:02d}:00-{kapanis:02d}:00 arası açık."
    bitis = bitis_saati(baslangic, makine["machine_type"], program)
    if bitis > baslangic.replace(hour=kapanis, minute=0, second=0):
        return f"Bu randevu {bitis:%H:%M}'de biterdi; çamaşırhane {kapanis:02d}:00'de kapanıyor."

    if makine["out_of_order"]:
        return "Bu makine arızalı."
    if makine["machine_type"] == "washer" and program not in PROGRAMLAR:
        return "Çamaşır makinesi için bir program seçmelisin."
    return None


def iptal_edilebilir_mi(randevu, simdi):
    """Yalnızca aktif ve henüz başlamamış randevular iptal edilir."""
    return randevu["status"] == "active" and randevu["start_time"] > simdi.strftime("%Y-%m-%d %H:%M:%S")


def kurutma_onerisi_olur_mu(camasir_bitisi, simdi):
    """Çamaşır bitince kurutma önerilir: kurutma kapanışa yetişiyor ve randevu penceresindeyse."""
    return (camasir_bitisi.hour + SURELER["dryer"] <= calisma_saatleri(camasir_bitisi)[1]
            and camasir_bitisi.date() <= son_rezervasyon_gunu(simdi))


# ---- Çalışan çamaşır ----

# Biten çamaşır bu süre boyunca ana ekranda "hazır" olarak gösterilir (makineden alınması hatırlatılır)
HAZIR_GOSTERIM_SURESI = timedelta(minutes=30)


def yikama_durumu(baslangic, bitis, simdi):
    """Çalışan/biten çamaşırın durumu: toplam ve kalan saniye, ilerleme (0-1), bitti mi."""
    toplam = max(int((bitis - baslangic).total_seconds()), 1)
    kalan = max(int((bitis - simdi).total_seconds()), 0)
    return {"toplam_sn": toplam, "kalan_sn": kalan, "ilerleme": round(1 - kalan / toplam, 4), "bitti": kalan == 0}


# ---- Zaman şeridi ----

def serit_hesapla(makineler, randevular, gun, simdi, student_id):
    """Zaman şeridi: her makine için günün saatleri ve durumları.
    randevular: [(machine_id, baslangic, bitis, student_id)] (o günün aktif randevuları).
    Durumlar: gecmis | dolu | benim (kendi randevun) | uygun (randevu başlatılabilir) | bos (boş ama süre sığmıyor) | ariza
    Çamaşır makinesinde "uygun" en kısa programa (renkli) göredir; beyazın sığdığı saatler beyaz_sigan_saatler ile bulunur."""
    acilis, kapanis = calisma_saatleri(gun)
    gun = gun.replace(hour=0, minute=0, second=0, microsecond=0)
    makine_randevulari = {}
    for machine_id, bas, bit, sahip in randevular:
        makine_randevulari.setdefault(machine_id, []).append((bas, bit, sahip))

    def sahibi(machine_id, saat):
        bas, bit = gun.replace(hour=saat), gun.replace(hour=saat) + timedelta(hours=1)
        return next((s for r_bas, r_bit, s in makine_randevulari.get(machine_id, []) if r_bas < bit and r_bit > bas), None)

    serit = {}
    for m in makineler:
        sure = randevu_suresi(m["machine_type"], None)
        hucreler = []
        for saat in range(acilis, kapanis):
            kimin = sahibi(m["machine_id"], saat)
            if m["out_of_order"]:
                durum = "ariza"
            elif gun.replace(hour=saat) <= simdi:
                durum = "gecmis"
            elif kimin is not None:
                durum = "benim" if kimin == student_id else "dolu"
            elif saat + sure <= kapanis and all(sahibi(m["machine_id"], saat + k) is None for k in range(sure)):
                durum = "uygun"
            else:
                durum = "bos"
            hucreler.append((saat, durum))
        serit[m["machine_id"]] = hucreler
    return serit


def beyaz_sigan_saatler(hucreler):
    """Beyaz yıkama (2 saat) için o saat ve bir sonraki saat boş olmalı."""
    durumlar = dict(hucreler)
    ek = SURELER["white"] - SURELER["colored"]
    return {h for h, d in hucreler if d == "uygun" and all(durumlar.get(h + k) == "uygun" for k in range(1, ek + 1))}


# ---- Form doğrulama ----

def ogrenci_alanlarini_dogrula(form, alan_adlari):
    """Kayıt ve profil düzenlemede ortak: boşlukları atar, e-postayı küçültür, telefonu temizler.
    (alanlar, hata) döner; hata None ise alanlar kullanılabilir."""
    alanlar = {k: (form.get(k) or "").strip() for k in alan_adlari}
    if "email" in alanlar:
        alanlar["email"] = alanlar["email"].lower()
    if "phone" in alanlar:
        alanlar["phone"] = re.sub(r"[\s()-]", "", alanlar["phone"])

    if not all(alanlar.values()):
        return alanlar, "Boş alan bırakılamaz."
    if "email" in alanlar and not EPOSTA_KALIBI.fullmatch(alanlar["email"]):
        return alanlar, "Geçerli bir e-posta adresi girin."
    if "phone" in alanlar and not TELEFON_KALIBI.fullmatch(alanlar["phone"]):
        return alanlar, "Telefon numarası 10-15 rakam olmalı (ör. 05551234567)."
    return alanlar, None


def foto_uzantisi(veri):
    """Dosyanın ilk baytlarına göre 'jpg' | 'png' | 'webp'; resim değilse None."""
    if veri[:4] == b"RIFF" and veri[8:12] == b"WEBP":
        return "webp"
    return next((u for imza, u in FOTO_IMZALARI.items() if veri.startswith(imza)), None)
