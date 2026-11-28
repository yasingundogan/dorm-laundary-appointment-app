from werkzeug.security import generate_password_hash
import sqlite3
import random
from datetime import datetime

import kurallar
import migrations
import os


random.seed(48)

# Geliştirme verisi: veritabanı silinip geçişlerle (migrations/) boştan kurulur, sonra örnek veri eklenir
if os.path.exists("camasirhane.db"):
    os.remove("camasirhane.db")
migrations.uygula("camasirhane.db")

conn = sqlite3.connect("camasirhane.db")   # veritabanı dosyasına bağlan
conn.execute("PRAGMA foreign_keys = ON")    # foreign key kontrolünü aç



# Merkez Yurdu'nun 4 bloğu, her bloğun kendi çamaşırhanesi (A Blok migrations/001'de 1 numara olarak var)
BLOKLAR = ["A", "B", "C", "D"]
for blok in BLOKLAR[1:]:
    conn.execute("insert into laundry_rooms (dorm_name, block_name) values ('Merkez Yurdu', ?)", (f"{blok} Blok",))

# Toplam 30 çamaşır + 15 kurutma makinesi bloklara dağıtılır; numaralar her çamaşırhanede 1'den başlar
CAMASIR = {"A": 8, "B": 7, "C": 8, "D": 7}
KURUTMA = {"A": 4, "B": 4, "C": 4, "D": 3}
blok_camasir_makineleri = {}
for i, blok in enumerate(BLOKLAR, start=1):
    blok_camasir_makineleri[blok] = [
        conn.execute("insert into machines (laundry_room_id, machine_no, machine_type) values (?, ?, 'washer')",
                     (i, num)).lastrowid
        for num in range(1, CAMASIR[blok] + 1)
    ]
for i, blok in enumerate(BLOKLAR, start=1):
    for num in range(1, KURUTMA[blok] + 1):
        conn.execute("insert into machines (laundry_room_id, machine_no, machine_type) values (?, ?, 'dryer')", (i, num))

first_names = ["Ayse", "Zeynep", "Elif", "Nisa", "Eylul", "Fatma" , "Busra" , "Maya"]
last_names = ["Yilmaz", "Kaya", "Demir", "Celik", "Sahin" , "Yildiz" , "Kara" , "Yildirim"]

TEST_SIFRESI = "test1234"
sifre_hash = generate_password_hash(TEST_SIFRESI)
ogrenci_bloklari = {}
for i in range(1, 1001):
    ad = random.choice(first_names)
    soyad = random.choice(last_names)
    email = f"ogrenci{i}@ornek.com"
    telefon = f"0532{i:07d}"
    
    

    blok = random.choice(BLOKLAR)
    ogrenci_bloklari[i] = blok
    kat = random.randint(1, 5)
    oda = random.randint(1, 20)
    oda_no = f"{blok}-{kat}{oda:02d}"      # örnek: "B-204"

    conn.execute(
        "insert into students (student_name, student_surname, student_mail , student_phone_no , room_no , student_password_hash, laundry_room_id) values (?, ?, ?, ?, ? ,?, ?)",
        (ad , soyad , email , telefon , oda_no , sifre_hash, BLOKLAR.index(blok) + 1)
    )

gunler = [
    ("2026-10-05", False),   # pazartesi
    ("2026-10-06", False),
    ("2026-10-07", False),
    ("2026-10-08", False),
    ("2026-10-09", False),   # cuma
    ("2026-10-10", True),    # cumartesi
    ("2026-10-11", True),    # pazar
]



eklenen = 0
atlanan = 0

for student_id in range(1, 1001):
    yikama_sayisi = random.choice([0, 1, 2])
    for _ in range(yikama_sayisi):
        gun, hafta_sonu = random.choice(gunler)

        if hafta_sonu:
            saat = random.randint(9, 16)
        else:
            saat = random.randint(8 , 19)

        start_time = f"{gun} {saat:02d}:00:00"
        machine_id = random.choice(blok_camasir_makineleri[ogrenci_bloklari[student_id]])   # kendi bloğunun çamaşır makinesi
        program = random.choice(['white' , 'colored'])                               # "colored" ya da "white"

        try:
            conn.execute(
                "insert into appointments (student_id, machine_id, start_time, end_time, program) values (?, ?, ?, ?, ?)",
                (student_id , machine_id , start_time ,
                 kurallar.bitis_saati(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S"), "washer", program).strftime("%Y-%m-%d %H:%M:%S"),
                 program)
            )
            eklenen += 1
        except sqlite3.IntegrityError:
            atlanan += 1

print("Eklenen randevu:", eklenen)
print("Çakışma yüzünden atlanan:", atlanan)

sonuc = conn.execute("select count(*) from machines").fetchone()
print(sonuc)

ogrenciler = conn.execute("select student_name from students limit 5").fetchall()
for ogrenci in ogrenciler:
    print(ogrenci)

print(conn.execute("select min(start_time), max(start_time) from appointments").fetchone())




conn.commit()   # değişiklikleri kaydet
conn.close()    # bağlantıyı kapat

